import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

# Page configuration
st.set_page_config(
    page_title="Marken Digital Transformation - Editable Estimation Tool",
    page_icon="📊",
    layout="wide"
)

# Initialize session state for editable data
if 'rate_card' not in st.session_state:
    st.session_state.rate_card = {
        'Onsite': {
            'Head of Technology': 140.00,
            'Senior Technical Architect': 113.26,
            'Technical Architect': 102.56,
            'Project Manager': 102.56,
            'Senior Developer': 87.40,
            'Developer': 82.05,
            'Senior Tester': 82.94,
            'Team Lead': 89.18,
            'DevOps Engineer': 87.40,
            'Business Analyst': 82.05,
            'Scrum Master': 89.18,
            'UI/UX Designer': 82.05,
            'Mobile Developer': 87.40,
            'Integration Specialist': 89.18,
            'Data Architect': 102.56
        },
        'Nearshore': {
            'Senior Technical Architect': 75.12,
            'Technical Architect': 68.02,
            'Project Manager': 68.02,
            'Senior Developer': 57.97,
            'Developer': 54.42,
            'Tester': 51.46,
            'Senior Tester': 55.01,
            'Team Lead': 59.15,
            'DevOps Engineer': 57.97,
            'Automation Test Lead': 59.15,
            'UI/UX Developer': 54.42,
            'Business Analyst': 54.42,
            'Mobile Developer': 57.97,
            'Integration Developer': 57.97,
            'Performance Engineer': 57.97,
            'QA Lead': 55.01
        },
        'Offshore': {
            'Technical Architect': 26.75,
            'Senior Developer': 23.19,
            'Developer': 20.51,
            'Junior Developer': 18.73,
            'Tester': 19.62,
            'Senior Tester': 22.30,
            'Automation Tester': 22.30,
            'Performance Tester': 22.30,
            'Technical Writer': 18.73,
            'Database Developer': 23.19,
            'Integration Developer': 23.19,
            'QA Analyst': 19.62,
            'Support Engineer': 18.73,
            'DevOps Engineer': 23.19,
            'Data Engineer': 23.19
        }
    }

if 'resources' not in st.session_state:
    st.session_state.resources = {
        'Phase 0': {
            'duration_weeks': 8,
            'Onsite': {
                'Head of Technology': 1,
                'Senior Technical Architect': 2,
                'Business Analyst': 2,
                'UI/UX Designer': 1
            },
            'Nearshore': {},
            'Offshore': {}
        },
        'Phase 1': {
            'duration_weeks': 28,
            'Onsite': {
                'Senior Technical Architect': 2,
                'Technical Architect': 2,
                'Project Manager': 2,
                'Senior Developer': 3,
                'Team Lead': 2,
                'DevOps Engineer': 2,
                'Business Analyst': 2,
                'Integration Specialist': 1
            },
            'Nearshore': {
                'Technical Architect': 2,
                'Senior Developer': 4,
                'Mobile Developer': 3,
                'Developer': 6,
                'Senior Tester': 3,
                'Automation Test Lead': 2,
                'UI/UX Developer': 3,
                'DevOps Engineer': 1,
                'Integration Developer': 2,
                'Performance Engineer': 1
            },
            'Offshore': {
                'Senior Developer': 4,
                'Developer': 8,
                'Junior Developer': 4,
                'Integration Developer': 3,
                'Tester': 6,
                'Automation Tester': 3,
                'Performance Tester': 2,
                'Database Developer': 2,
                'Technical Writer': 2,
                'DevOps Engineer': 2,
                'Data Engineer': 2
            }
        },
        'Phase 2': {
            'duration_weeks': 16,
            'Onsite': {
                'Technical Architect': 1,
                'Project Manager': 1,
                'Senior Developer': 2,
                'Team Lead': 1,
                'Business Analyst': 1,
                'Data Architect': 1
            },
            'Nearshore': {
                'Senior Developer': 2,
                'Developer': 3,
                'Senior Tester': 1,
                'Automation Test Lead': 1,
                'UI/UX Developer': 2,
                'QA Lead': 1
            },
            'Offshore': {
                'Developer': 4,
                'Junior Developer': 2,
                'Tester': 3,
                'Automation Tester': 1,
                'QA Analyst': 2,
                'Technical Writer': 1,
                'Support Engineer': 2
            }
        }
    }

def calculate_cost_for_phase(phase_name):
    """Calculate cost for a specific phase"""
    resources = st.session_state.resources[phase_name]
    duration_weeks = resources['duration_weeks']
    total_cost = 0
    hours_per_week = 40
    
    for location in ['Onsite', 'Nearshore', 'Offshore']:
        for role, count in resources[location].items():
            if role in st.session_state.rate_card[location]:
                rate = st.session_state.rate_card[location][role]
            else:
                # Default rates
                rate = 50 if location == 'Offshore' else 75 if location == 'Nearshore' else 100
            total_cost += count * rate * hours_per_week * duration_weeks
    
    return total_cost

def get_team_size(phase_name):
    """Get total team size for a phase"""
    resources = st.session_state.resources[phase_name]
    total = 0
    for location in ['Onsite', 'Nearshore', 'Offshore']:
        total += sum(resources[location].values())
    return total

def save_configuration():
    """Save current configuration to JSON"""
    config = {
        'rate_card': st.session_state.rate_card,
        'resources': st.session_state.resources
    }
    return json.dumps(config, indent=2)

def load_configuration(config_json):
    """Load configuration from JSON"""
    try:
        config = json.loads(config_json)
        st.session_state.rate_card = config['rate_card']
        st.session_state.resources = config['resources']
        return True
    except:
        return False

# Main App
st.title("🚀 Marken Digital Transformation - Editable Estimation Tool")
st.markdown("### Customize Resources and Rates for Each Phase")

# Sidebar for quick actions
with st.sidebar:
    st.header("⚙️ Quick Actions")
    
    # Contingency setting
    contingency = st.slider("Contingency %", 0, 30, 20, key='contingency')
    
    st.markdown("---")
    
    # Save/Load configuration
    st.subheader("📁 Configuration")
    
    if st.button("💾 Download Configuration"):
        config_json = save_configuration()
        st.download_button(
            label="Download as JSON",
            data=config_json,
            file_name=f"marken_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    uploaded_file = st.file_uploader("Upload Configuration", type=['json'])
    if uploaded_file is not None:
        config_content = uploaded_file.read().decode('utf-8')
        if load_configuration(config_content):
            st.success("Configuration loaded successfully!")
            st.rerun()
        else:
            st.error("Failed to load configuration")
    
    st.markdown("---")
    
    # Quick metrics
    st.subheader("📊 Quick Metrics")
    total_cost = sum(calculate_cost_for_phase(f"Phase {i}") for i in range(3))
    st.metric("Total Base Cost", f"${total_cost:,.0f}")
    st.metric("With Contingency", f"${total_cost * (1 + contingency/100):,.0f}")

# Main tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Dashboard", 
    "👥 Edit Resources", 
    "💵 Edit Rates", 
    "📈 Analysis", 
    "📋 Resource Summary",
    "🎯 Skill Requirements"
])

with tab1:
    st.header("Executive Dashboard")
    
    # Calculate metrics for all phases
    phase_data = []
    for phase_num in range(3):
        phase_name = f"Phase {phase_num}"
        cost = calculate_cost_for_phase(phase_name)
        team_size = get_team_size(phase_name)
        duration = st.session_state.resources[phase_name]['duration_weeks']
        
        phase_data.append({
            'Phase': phase_name,
            'Duration (weeks)': duration,
            'Team Size': team_size,
            'Base Cost': cost,
            'Contingency': cost * (contingency/100),
            'Total Cost': cost * (1 + contingency/100),
            'Weekly Burn': cost / duration if duration > 0 else 0
        })
    
    df_phases = pd.DataFrame(phase_data)
    
    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_duration = sum(p['Duration (weeks)'] for p in phase_data)
        st.metric("Total Duration", f"{total_duration} weeks")
        st.caption(f"~{total_duration/4.33:.1f} months")
    
    with col2:
        total_cost = sum(p['Total Cost'] for p in phase_data)
        st.metric("Total Investment", f"${total_cost/1000000:.2f}M")
        st.caption(f"Includes {contingency}% contingency")
    
    with col3:
        peak_team = max(p['Team Size'] for p in phase_data)
        peak_phase = phase_data[[p['Team Size'] for p in phase_data].index(peak_team)]['Phase']
        st.metric("Peak Team Size", f"{peak_team}")
        st.caption(f"During {peak_phase}")
    
    with col4:
        avg_burn = sum(p['Weekly Burn'] for p in phase_data) / len(phase_data)
        st.metric("Avg Weekly Burn", f"${avg_burn:,.0f}")
        st.caption("Across all phases")
    
    # Phase summary table
    st.subheader("Phase-by-Phase Summary")
    st.dataframe(
        df_phases.style.format({
            'Base Cost': '${:,.0f}',
            'Contingency': '${:,.0f}',
            'Total Cost': '${:,.0f}',
            'Weekly Burn': '${:,.0f}'
        }).background_gradient(subset=['Total Cost', 'Team Size']),
        use_container_width=True
    )
    
    # Cost breakdown chart
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.bar(
            df_phases,
            x='Phase',
            y='Total Cost',
            title='Cost by Phase',
            color='Total Cost',
            color_continuous_scale='Blues'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.pie(
            df_phases,
            values='Team Size',
            names='Phase',
            title='Team Size Distribution'
        )
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Edit Resources by Phase")
    
    phase_select = st.selectbox("Select Phase", ["Phase 0", "Phase 1", "Phase 2"])
    
    # Duration editor
    st.subheader(f"⏱️ {phase_select} Duration")
    new_duration = st.number_input(
        "Duration (weeks)",
        min_value=1,
        max_value=52,
        value=st.session_state.resources[phase_select]['duration_weeks']
    )
    st.session_state.resources[phase_select]['duration_weeks'] = new_duration
    
    st.markdown("---")
    
    # Resource editors for each location
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("🏢 Onsite Resources")
        onsite_resources = st.session_state.resources[phase_select]['Onsite'].copy()
        
        # Add new role
        with st.expander("Add New Role"):
            available_roles = [r for r in st.session_state.rate_card['Onsite'].keys() 
                             if r not in onsite_resources]
            if available_roles:
                new_role = st.selectbox("Select Role", available_roles, key=f"onsite_new_{phase_select}")
                new_count = st.number_input("Count", min_value=1, value=1, key=f"onsite_count_{phase_select}")
                if st.button("Add", key=f"onsite_add_{phase_select}"):
                    st.session_state.resources[phase_select]['Onsite'][new_role] = new_count
                    st.rerun()
        
        # Edit existing roles
        for role in list(onsite_resources.keys()):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                new_count = st.number_input(
                    role,
                    min_value=0,
                    value=onsite_resources[role],
                    key=f"onsite_{phase_select}_{role}"
                )
                if new_count == 0:
                    del st.session_state.resources[phase_select]['Onsite'][role]
                else:
                    st.session_state.resources[phase_select]['Onsite'][role] = new_count
            with col_b:
                rate = st.session_state.rate_card['Onsite'].get(role, 100)
                st.caption(f"${rate}/hr")
    
    with col2:
        st.subheader("🌍 Nearshore Resources")
        nearshore_resources = st.session_state.resources[phase_select]['Nearshore'].copy()
        
        # Add new role
        with st.expander("Add New Role"):
            available_roles = [r for r in st.session_state.rate_card['Nearshore'].keys() 
                             if r not in nearshore_resources]
            if available_roles:
                new_role = st.selectbox("Select Role", available_roles, key=f"nearshore_new_{phase_select}")
                new_count = st.number_input("Count", min_value=1, value=1, key=f"nearshore_count_{phase_select}")
                if st.button("Add", key=f"nearshore_add_{phase_select}"):
                    st.session_state.resources[phase_select]['Nearshore'][new_role] = new_count
                    st.rerun()
        
        # Edit existing roles
        for role in list(nearshore_resources.keys()):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                new_count = st.number_input(
                    role,
                    min_value=0,
                    value=nearshore_resources[role],
                    key=f"nearshore_{phase_select}_{role}"
                )
                if new_count == 0:
                    del st.session_state.resources[phase_select]['Nearshore'][role]
                else:
                    st.session_state.resources[phase_select]['Nearshore'][role] = new_count
            with col_b:
                rate = st.session_state.rate_card['Nearshore'].get(role, 75)
                st.caption(f"${rate}/hr")
    
    with col3:
        st.subheader("🌏 Offshore Resources")
        offshore_resources = st.session_state.resources[phase_select]['Offshore'].copy()
        
        # Add new role
        with st.expander("Add New Role"):
            available_roles = [r for r in st.session_state.rate_card['Offshore'].keys() 
                             if r not in offshore_resources]
            if available_roles:
                new_role = st.selectbox("Select Role", available_roles, key=f"offshore_new_{phase_select}")
                new_count = st.number_input("Count", min_value=1, value=1, key=f"offshore_count_{phase_select}")
                if st.button("Add", key=f"offshore_add_{phase_select}"):
                    st.session_state.resources[phase_select]['Offshore'][new_role] = new_count
                    st.rerun()
        
        # Edit existing roles
        for role in list(offshore_resources.keys()):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                new_count = st.number_input(
                    role,
                    min_value=0,
                    value=offshore_resources[role],
                    key=f"offshore_{phase_select}_{role}"
                )
                if new_count == 0:
                    del st.session_state.resources[phase_select]['Offshore'][role]
                else:
                    st.session_state.resources[phase_select]['Offshore'][role] = new_count
            with col_b:
                rate = st.session_state.rate_card['Offshore'].get(role, 50)
                st.caption(f"${rate}/hr")
    
    # Show updated cost for this phase
    st.markdown("---")
    phase_cost = calculate_cost_for_phase(phase_select)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Phase Base Cost", f"${phase_cost:,.0f}")
    with col2:
        st.metric("With Contingency", f"${phase_cost * (1 + contingency/100):,.0f}")
    with col3:
        team_size = get_team_size(phase_select)
        st.metric("Total Team Size", team_size)

with tab3:
    st.header("Edit Rate Cards")
    
    location_select = st.selectbox("Select Location", ["Onsite", "Nearshore", "Offshore"])
    
    st.subheader(f"💵 {location_select} Rates (USD per hour)")
    
    # Add new role to rate card
    with st.expander("Add New Role"):
        new_role_name = st.text_input("Role Name")
        new_role_rate = st.number_input("Hourly Rate (USD)", min_value=10.0, value=50.0, step=0.5)
        if st.button("Add Role") and new_role_name:
            st.session_state.rate_card[location_select][new_role_name] = new_role_rate
            st.rerun()
    
    # Edit existing rates
    rates = st.session_state.rate_card[location_select].copy()
    
    # Display in two columns for better layout
    col1, col2 = st.columns(2)
    roles_list = list(rates.keys())
    mid_point = len(roles_list) // 2
    
    with col1:
        for role in roles_list[:mid_point]:
            new_rate = st.number_input(
                role,
                min_value=10.0,
                value=float(rates[role]),
                step=0.5,
                key=f"rate_{location_select}_{role}"
            )
            st.session_state.rate_card[location_select][role] = new_rate
    
    with col2:
        for role in roles_list[mid_point:]:
            new_rate = st.number_input(
                role,
                min_value=10.0,
                value=float(rates[role]),
                step=0.5,
                key=f"rate_{location_select}_{role}"
            )
            st.session_state.rate_card[location_select][role] = new_rate
    
    # Show rate comparison
    st.markdown("---")
    st.subheader("Rate Comparison Across Locations")
    
    # Find common roles
    common_roles = set()
    for loc in ['Onsite', 'Nearshore', 'Offshore']:
        common_roles.update(st.session_state.rate_card[loc].keys())
    
    comparison_data = []
    for role in sorted(common_roles):
        comparison_data.append({
            'Role': role,
            'Onsite': st.session_state.rate_card['Onsite'].get(role, 0),
            'Nearshore': st.session_state.rate_card['Nearshore'].get(role, 0),
            'Offshore': st.session_state.rate_card['Offshore'].get(role, 0)
        })
    
    df_comparison = pd.DataFrame(comparison_data)
    df_comparison['Savings (Nearshore)'] = ((df_comparison['Onsite'] - df_comparison['Nearshore']) / df_comparison['Onsite'] * 100).round(1)
    df_comparison['Savings (Offshore)'] = ((df_comparison['Onsite'] - df_comparison['Offshore']) / df_comparison['Onsite'] * 100).round(1)
    
    st.dataframe(
        df_comparison.style.format({
            'Onsite': '${:.2f}',
            'Nearshore': '${:.2f}',
            'Offshore': '${:.2f}',
            'Savings (Nearshore)': '{:.1f}%',
            'Savings (Offshore)': '{:.1f}%'
        }).background_gradient(subset=['Onsite', 'Nearshore', 'Offshore']),
        use_container_width=True
    )

with tab4:
    st.header("Resource & Cost Analysis")
    
    # Resource distribution across phases
    st.subheader("Resource Distribution")
    
    distribution_data = []
    for phase_num in range(3):
        phase_name = f"Phase {phase_num}"
        resources = st.session_state.resources[phase_name]
        distribution_data.append({
            'Phase': phase_name,
            'Onsite': sum(resources['Onsite'].values()),
            'Nearshore': sum(resources['Nearshore'].values()),
            'Offshore': sum(resources['Offshore'].values())
        })
    
    df_dist = pd.DataFrame(distribution_data)
    
    # Stacked bar chart
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Onsite', x=df_dist['Phase'], y=df_dist['Onsite']))
    fig.add_trace(go.Bar(name='Nearshore', x=df_dist['Phase'], y=df_dist['Nearshore']))
    fig.add_trace(go.Bar(name='Offshore', x=df_dist['Phase'], y=df_dist['Offshore']))
    fig.update_layout(barmode='stack', title='Resource Stack by Phase')
    st.plotly_chart(fig, use_container_width=True)
    
    # Cost breakdown by location
    st.subheader("Cost Breakdown by Location")
    
    cost_breakdown = []
    for phase_num in range(3):
        phase_name = f"Phase {phase_num}"
        resources = st.session_state.resources[phase_name]
        duration = resources['duration_weeks']
        
        for location in ['Onsite', 'Nearshore', 'Offshore']:
            location_cost = 0
            for role, count in resources[location].items():
                rate = st.session_state.rate_card[location].get(role, 50)
                location_cost += count * rate * 40 * duration
            
            if location_cost > 0:
                cost_breakdown.append({
                    'Phase': phase_name,
                    'Location': location,
                    'Cost': location_cost
                })
    
    df_cost_breakdown = pd.DataFrame(cost_breakdown)
    
    fig = px.sunburst(
        df_cost_breakdown,
        path=['Phase', 'Location'],
        values='Cost',
        title='Cost Distribution Hierarchy'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Efficiency metrics
    st.subheader("Efficiency Metrics")
    
    efficiency_data = []
    for phase_num in range(3):
        phase_name = f"Phase {phase_num}"
        cost = calculate_cost_for_phase(phase_name)
        team_size = get_team_size(phase_name)
        duration = st.session_state.resources[phase_name]['duration_weeks']
        
        efficiency_data.append({
            'Phase': phase_name,
            'Cost per Person-Week': cost / (team_size * duration) if team_size > 0 and duration > 0 else 0,
            'Average Team Cost/Hour': cost / (team_size * duration * 40) if team_size > 0 and duration > 0 else 0,
            'Team Productivity': 1000 / (cost / (team_size * duration)) if cost > 0 and team_size > 0 and duration > 0 else 0
        })
    
    df_efficiency = pd.DataFrame(efficiency_data)
    
    col1, col2, col3 = st.columns(3)
    for i, phase in enumerate(efficiency_data):
        with [col1, col2, col3][i]:
            st.metric(
                f"{phase['Phase']} Efficiency",
                f"${phase['Cost per Person-Week']:,.0f}",
                f"Avg: ${phase['Average Team Cost/Hour']:.2f}/hr"
            )

with tab5:
    st.header("📋 Complete Resource Summary")
    
    # Create comprehensive resource table
    all_resources = []
    
    for phase_num in range(3):
        phase_name = f"Phase {phase_num}"
        resources = st.session_state.resources[phase_name]
        duration = resources['duration_weeks']
        
        for location in ['Onsite', 'Nearshore', 'Offshore']:
            for role, count in resources[location].items():
                if count > 0:
                    rate = st.session_state.rate_card[location].get(role, 50)
                    total_cost = count * rate * 40 * duration
                    
                    all_resources.append({
                        'Phase': phase_name,
                        'Location': location,
                        'Role': role,
                        'Count': count,
                        'Rate/Hour': rate,
                        'Duration (weeks)': duration,
                        'Total Hours': count * 40 * duration,
                        'Total Cost': total_cost
                    })
    
    df_all_resources = pd.DataFrame(all_resources)
    
    # Display by phase
    for phase_num in range(3):
        phase_name = f"Phase {phase_num}"
        st.subheader(f"{phase_name} Resources")
        
        phase_df = df_all_resources[df_all_resources['Phase'] == phase_name]
        
        if not phase_df.empty:
            # Summary metrics for this phase
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                total_people = phase_df['Count'].sum()
                st.metric("Total People", total_people)
            with col2:
                total_hours = phase_df['Total Hours'].sum()
                st.metric("Total Hours", f"{total_hours:,}")
            with col3:
                total_cost = phase_df['Total Cost'].sum()
                st.metric("Total Cost", f"${total_cost:,.0f}")
            with col4:
                avg_rate = phase_df['Total Cost'].sum() / phase_df['Total Hours'].sum()
                st.metric("Avg Rate", f"${avg_rate:.2f}/hr")
            
            # Detailed table
            st.dataframe(
                phase_df.style.format({
                    'Rate/Hour': '${:.2f}',
                    'Total Hours': '{:,.0f}',
                    'Total Cost': '${:,.0f}'
                }),
                use_container_width=True
            )
        
        st.markdown("---")
    
    # Download full resource plan
    if st.button("📥 Export Full Resource Plan"):
        st.download_button(
            label="Download as CSV",
            data=df_all_resources.to_csv(index=False),
            file_name=f"marken_resources_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

with tab6:
    st.header("🎯 Skill Requirements by Phase")
    
    st.markdown("""
    ### Phase-wise Skill Distribution and Technical Requirements
    """)
    
    # Phase 0 Skills
    with st.expander("📋 **Phase 0 - Due Diligence** (8 weeks)"):
        st.markdown("""
        **Core Focus:** Architecture Design, POCs, Business Alignment
        
        **Required Skillsets:**
        - **Enterprise Architecture:** Microservices, Event-driven architecture, API design
        - **Cloud Architecture:** AWS/Azure, Kubernetes, Docker
        - **Integration Patterns:** ESB, API Gateway, Event streaming (Kafka)
        - **Mobile Architecture:** Android development for Zebra scanners
        - **IoT Architecture:** Temperature sensors, real-time data streaming
        - **Business Analysis:** Process mapping, requirements gathering
        - **UI/UX Design:** Design systems, mobile-first approach
        
        **Key Deliverables:**
        - Technical architecture blueprint
        - Integration strategy document
        - POC for Zebra scanner app
        - POC for IoT temperature monitoring
        - Risk assessment and mitigation plan
        """)
    
    # Phase 1 Skills
    with st.expander("🚀 **Phase 1 - Polar Scan & Track** (28 weeks)"):
        st.markdown("""
        **Core Focus:** Mobile App, Real-time Systems, IoT Integration
        
        **Technical Stack & Skills Required:**
        
        **Frontend Development:**
        - React/Angular for web applications
        - React Native for cross-platform mobile
        - Android native (Java/Kotlin) for Zebra scanner
        - Progressive Web Apps (PWA)
        - Responsive design, Material Design
        
        **Backend Development:**
        - Microservices (Node.js, Java Spring Boot)
        - RESTful APIs and GraphQL
        - Event-driven architecture (Kafka, RabbitMQ)
        - Real-time processing (WebSockets, Server-Sent Events)
        - Caching strategies (Redis)
        
        **Mobile Development (Critical for Phase 1):**
        - Android SDK for Zebra devices
        - Barcode scanning libraries (ZXing)
        - Offline-first architecture
        - Background services and sync
        - Hardware integration (scanner, printer)
        
        **IoT & Real-time Systems:**
        - IoT protocols (MQTT, CoAP)
        - Temperature sensor integration
        - GPS/Telematics integration
        - Real-time data pipelines
        - Time-series databases (InfluxDB)
        
        **Integration & Middleware:**
        - API Gateway (Kong, Apigee)
        - ESB/Integration platforms
        - EDI processing
        - WMS/ERP integration (Dynamics 365)
        - Third-party APIs (FedEx, UPS, DHL)
        
        **DevOps & Infrastructure:**
        - CI/CD pipelines (Jenkins, GitLab CI)
        - Container orchestration (Kubernetes)
        - Infrastructure as Code (Terraform)
        - Monitoring (Prometheus, Grafana)
        - Log aggregation (ELK stack)
        
        **Data & Analytics:**
        - PostgreSQL, MongoDB, Redis
        - Data warehousing
        - ETL pipelines
        - Business intelligence tools
        - Predictive analytics for route optimization
        
        **Testing & Quality:**
        - Mobile app testing (Appium)
        - API testing (Postman, REST Assured)
        - Performance testing (JMeter, Gatling)
        - Security testing
        - Test automation frameworks
        """)
    
    # Phase 2 Skills
    with st.expander("💊 **Phase 2 - Patient Management** (16 weeks)"):
        st.markdown("""
        **Core Focus:** Web Portal, NHS Integration, Compliance
        
        **Technical Stack & Skills Required:**
        
        **Frontend Development:**
        - React/Angular for patient portal
        - Accessibility standards (WCAG)
        - Responsive design
        - Form validation and wizards
        - Dashboard and reporting UI
        
        **Backend Development:**
        - CRUD operations
        - Workflow engines
        - Business rules engine
        - Notification services
        - Document management
        
        **Healthcare Integration:**
        - NHS API integration
        - HL7/FHIR standards
        - Electronic prescription handling
        - Clinical data exchange
        - Patient identity management
        
        **Security & Compliance:**
        - GDPR compliance implementation
        - GDP (Good Distribution Practice)
        - OAuth 2.0/SAML authentication
        - Data encryption at rest and transit
        - Audit logging
        - Role-based access control
        
        **Data Management:**
        - Master data management
        - Patient data privacy
        - Clinical data modeling
        - Report generation
        - Data archival strategies
        
        **Quality & Testing:**
        - Compliance testing
        - Security testing
        - User acceptance testing
        - Accessibility testing
        - Cross-browser testing
        """)
    
    # Skills Matrix
    st.markdown("---")
    st.subheader("📊 Skills Distribution Matrix")
    
    skills_matrix = {
        'Skill Category': [
            'Mobile Development',
            'Backend Development',
            'Frontend Web',
            'IoT/Real-time',
            'Integration',
            'DevOps/Cloud',
            'Testing/QA',
            'Business/Analysis',
            'Security/Compliance',
            'Data/Analytics'
        ],
        'Phase 0': ['Low', 'Medium', 'Low', 'Medium', 'High', 'High', 'Low', 'High', 'Medium', 'Low'],
        'Phase 1': ['Very High', 'Very High', 'High', 'Very High', 'Very High', 'High', 'High', 'Medium', 'Medium', 'High'],
        'Phase 2': ['Low', 'High', 'High', 'Low', 'Medium', 'Medium', 'High', 'Medium', 'Very High', 'Medium']
    }
    
    df_skills = pd.DataFrame(skills_matrix)
    
    # Color code the matrix
    def color_skill_level(val):
        colors = {
            'Low': 'background-color: #90EE90',
            'Medium': 'background-color: #FFD700',
            'High': 'background-color: #FFA500',
            'Very High': 'background-color: #FF6B6B'
        }
        return colors.get(val, '')
    
    st.dataframe(
        df_skills.style.applymap(color_skill_level, subset=['Phase 0', 'Phase 1', 'Phase 2']),
        use_container_width=True
    )
    
    st.info("""
    **Skills Legend:**
    - 🟩 **Low**: Minimal requirement or support role
    - 🟨 **Medium**: Standard requirement, moderate complexity
    - 🟠 **High**: Critical skill, significant effort needed
    - 🔴 **Very High**: Mission-critical, specialized expertise required
    """)
    
    # Critical Skills Alert
    st.warning("""
    **⚠️ Critical Skills for Success:**
    
    **Phase 1 Critical Skills:**
    - Android developers with Zebra scanner experience
    - IoT engineers for temperature monitoring
    - Real-time system architects
    - Mobile app performance optimization
    - Integration specialists for WMS/ERP
    
    **Phase 2 Critical Skills:**
    - NHS integration specialists
    - Healthcare compliance experts
    - GDPR/GDP compliance engineers
    - Clinical workflow designers
    """)

# Footer with summary
st.markdown("---")
st.markdown("### 💼 Project Summary")

total_cost = sum(calculate_cost_for_phase(f"Phase {i}") for i in range(3))
total_duration = sum(st.session_state.resources[f"Phase {i}"]['duration_weeks'] for i in range(3))
max_team_size = max(get_team_size(f"Phase {i}") for i in range(3))

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.info(f"**Total Duration:** {total_duration} weeks")
with col2:
    st.success(f"**Base Cost:** ${total_cost:,.0f}")
with col3:
    st.warning(f"**With {contingency}% Buffer:** ${total_cost * (1 + contingency/100):,.0f}")
with col4:
    st.error(f"**Peak Team:** {max_team_size} people")
