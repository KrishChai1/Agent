import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
from io import BytesIO
import numpy as np

# Page configuration with custom theme
st.set_page_config(
    page_title="SPLUS RTM Modernization Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
        background-color: #f0f2f6;
        border-radius: 5px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1f77b4;
        color: white;
    }
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        border: 1px solid #cccccc;
        padding: 5px 15px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .stExpander {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state for configuration
if 'config' not in st.session_state:
    st.session_state.config = {
        'program_duration': 24,  # Extended to 24 months for realistic timeline
        'contingency_percent': 20,  # Increased contingency
        'hourly_rates': {
            'onsite': {
                'Head of Technology': 140,
                'Senior Technical Architect': 113,
                'Technical Architect': 103,
                'Project Manager': 103,
                'Senior Developer': 87,
                'Team Lead': 89,
                'DevOps Engineer': 87,
                'Business Analyst': 82,
                'Integration Specialist': 89,
                'Solution Architect': 120,
                'Scrum Master': 95
            },
            'offshore': {
                'Senior Developer': 23,
                'Developer': 21,
                'Junior Developer': 19,
                'Integration Developer': 23,
                'Tester': 20,
                'Automation Tester': 22,
                'Performance Tester': 22,
                'DevOps Engineer': 25,
                'Business Analyst': 18,
                'Technical Lead': 28
            }
        },
        'hours_per_month': 160,
        'buffer_percent': 10  # Additional buffer for risk
    }

# Enhanced Phase configuration with realistic timeline
PHASES = {
    0: {
        'name': 'Discovery & Foundation',
        'duration': 3,  # Extended for proper setup
        'description': 'Architecture design, infrastructure setup, team onboarding',
        'deliverables': ['Cloud infrastructure', 'Development environment', 'CI/CD pipeline', 'Architecture blueprint'],
        'resources': {
            'onsite': {
                'Head of Technology': 1,
                'Senior Technical Architect': 2,
                'Solution Architect': 1,
                'DevOps Engineer': 1
            },
            'offshore': {
                'Senior Developer': 2,
                'DevOps Engineer': 2,
                'Technical Lead': 1
            }
        }
    },
    1: {
        'name': 'Core Platform & Customer Management',
        'duration': 4,  # Extended for complexity
        'description': 'Customer account management, user administration, core services',
        'deliverables': ['Customer Service', 'User Management', 'RBAC', 'API Gateway', 'CFW Portal'],
        'resources': {
            'onsite': {
                'Head of Technology': 1,
                'Senior Technical Architect': 1,
                'Technical Architect': 1,
                'Project Manager': 1,
                'Business Analyst': 1
            },
            'offshore': {
                'Technical Lead': 2,
                'Senior Developer': 3,
                'Developer': 6,
                'Tester': 3,
                'DevOps Engineer': 1
            }
        }
    },
    2: {
        'name': 'Order & Inventory Management',
        'duration': 4,
        'description': 'Order processing, inventory management, B2B integration',
        'deliverables': ['Order Service', 'Inventory Service', 'Activity Board', 'Review Board', 'B2B Platform'],
        'resources': {
            'onsite': {
                'Head of Technology': 1,
                'Senior Technical Architect': 1,
                'Technical Architect': 1,
                'Project Manager': 1,
                'Integration Specialist': 1,
                'Business Analyst': 1
            },
            'offshore': {
                'Technical Lead': 2,
                'Senior Developer': 4,
                'Developer': 8,
                'Integration Developer': 2,
                'Tester': 4,
                'Automation Tester': 2
            }
        }
    },
    3: {
        'name': 'Routing & Transportation',
        'duration': 4,
        'description': 'MORO integration, routing optimization, carrier integration',
        'deliverables': ['Routing Engine', 'MORO Integration', 'Carrier Services', 'Multi-modal Support'],
        'resources': {
            'onsite': {
                'Head of Technology': 1,
                'Senior Technical Architect': 1,
                'Technical Architect': 1,
                'Project Manager': 1,
                'Integration Specialist': 2
            },
            'offshore': {
                'Technical Lead': 2,
                'Senior Developer': 4,
                'Developer': 6,
                'Integration Developer': 3,
                'Tester': 3,
                'Automation Tester': 2
            }
        }
    },
    4: {
        'name': 'Vendor & Driver Management',
        'duration': 3,
        'description': 'Vendor lifecycle, driver mobile app, job assignment',
        'deliverables': ['Vendor Service', 'Driver Mobile App', 'Job Assignment', 'POD Management'],
        'resources': {
            'onsite': {
                'Head of Technology': 1,
                'Technical Architect': 1,
                'Project Manager': 1,
                'Business Analyst': 1
            },
            'offshore': {
                'Technical Lead': 2,
                'Senior Developer': 3,
                'Developer': 6,
                'Tester': 3,
                'Automation Tester': 1
            }
        }
    },
    5: {
        'name': 'Billing & Financial Systems',
        'duration': 3,
        'description': 'Billing engine, rate management, financial integrations',
        'deliverables': ['Billing Service', 'Rate Management', 'Storage Billing', 'E2K Integration'],
        'resources': {
            'onsite': {
                'Head of Technology': 1,
                'Technical Architect': 1,
                'Project Manager': 1,
                'Integration Specialist': 1
            },
            'offshore': {
                'Technical Lead': 1,
                'Senior Developer': 3,
                'Developer': 5,
                'Integration Developer': 2,
                'Tester': 3
            }
        }
    },
    6: {
        'name': 'Integration & Notifications',
        'duration': 2,
        'description': 'System integrations, notification platform',
        'deliverables': ['GIC/A2A Integration', 'EDI Management', 'WMS Integration', 'Notification Service'],
        'resources': {
            'onsite': {
                'Technical Architect': 1,
                'Integration Specialist': 2
            },
            'offshore': {
                'Technical Lead': 1,
                'Senior Developer': 2,
                'Integration Developer': 3,
                'Developer': 3,
                'Tester': 2
            }
        }
    },
    7: {
        'name': 'Advanced Features & Analytics',
        'duration': 2,
        'description': 'Analytics, reporting, service configuration',
        'deliverables': ['Analytics Dashboard', 'Reporting Engine', 'Service Configuration', 'Geographic Services'],
        'resources': {
            'onsite': {
                'Technical Architect': 1,
                'Business Analyst': 1
            },
            'offshore': {
                'Technical Lead': 1,
                'Senior Developer': 2,
                'Developer': 4,
                'Tester': 2
            }
        }
    },
    8: {
        'name': 'Testing, Migration & Deployment',
        'duration': 3,
        'description': 'End-to-end testing, data migration, production deployment',
        'deliverables': ['Performance Testing', 'Data Migration', 'Production Deployment', 'Training'],
        'resources': {
            'onsite': {
                'Head of Technology': 1,
                'Technical Architect': 1,
                'Project Manager': 1,
                'DevOps Engineer': 1
            },
            'offshore': {
                'Technical Lead': 2,
                'Senior Developer': 2,
                'Developer': 3,
                'Performance Tester': 3,
                'Automation Tester': 3,
                'DevOps Engineer': 2
            }
        }
    }
}

# Enhanced EPIC data with realistic complexity
def initialize_epic_data():
    return {
        'EPIC-001': {
            'name': 'Customer Account Management',
            'priority': 'P0',
            'phase': 1,
            'complexity': 'High',
            'risk': 'Medium',
            'dependencies': [],
            'estimated_months': 4,
            'story_points': 183
        },
        'EPIC-002': {
            'name': 'Order Management & Processing',
            'priority': 'P0',
            'phase': 2,
            'complexity': 'Very High',
            'risk': 'High',
            'dependencies': ['EPIC-001'],
            'estimated_months': 4,
            'story_points': 267
        },
        'EPIC-003': {
            'name': 'Inventory Management System',
            'priority': 'P0',
            'phase': 2,
            'complexity': 'Very High',
            'risk': 'High',
            'dependencies': ['EPIC-001', 'EPIC-007'],
            'estimated_months': 4,
            'story_points': 239
        },
        'EPIC-004': {
            'name': 'Routing & Transportation Engine',
            'priority': 'P0',
            'phase': 3,
            'complexity': 'Very High',
            'risk': 'Very High',
            'dependencies': ['EPIC-002'],
            'estimated_months': 4,
            'story_points': 248
        },
        'EPIC-005': {
            'name': 'Vendor & Driver Management',
            'priority': 'P1',
            'phase': 4,
            'complexity': 'High',
            'risk': 'Medium',
            'dependencies': ['EPIC-001'],
            'estimated_months': 3,
            'story_points': 197
        },
        'EPIC-006': {
            'name': 'Billing & Financial Management',
            'priority': 'P1',
            'phase': 5,
            'complexity': 'High',
            'risk': 'Medium',
            'dependencies': ['EPIC-002', 'EPIC-003'],
            'estimated_months': 3,
            'story_points': 204
        },
        'EPIC-007': {
            'name': 'Integration Platform',
            'priority': 'P0',
            'phase': 2,
            'complexity': 'Very High',
            'risk': 'Very High',
            'dependencies': [],
            'estimated_months': 4,
            'story_points': 276
        },
        'EPIC-008': {
            'name': 'Notification & Communication',
            'priority': 'P1',
            'phase': 6,
            'complexity': 'Medium',
            'risk': 'Low',
            'dependencies': ['EPIC-007'],
            'estimated_months': 2,
            'story_points': 134
        },
        'EPIC-009': {
            'name': 'Service & Activity Configuration',
            'priority': 'P2',
            'phase': 7,
            'complexity': 'Medium',
            'risk': 'Low',
            'dependencies': ['EPIC-002'],
            'estimated_months': 2,
            'story_points': 112
        },
        'EPIC-010': {
            'name': 'Geographic & Location Services',
            'priority': 'P2',
            'phase': 7,
            'complexity': 'Low',
            'risk': 'Low',
            'dependencies': [],
            'estimated_months': 1,
            'story_points': 68
        },
        'EPIC-011': {
            'name': 'Platform Infrastructure & Security',
            'priority': 'P0',
            'phase': 0,
            'complexity': 'Very High',
            'risk': 'Medium',
            'dependencies': [],
            'estimated_months': 3,
            'story_points': 181
        },
        'EPIC-012': {
            'name': 'Reporting & Analytics',
            'priority': 'P2',
            'phase': 7,
            'complexity': 'Medium',
            'risk': 'Low',
            'dependencies': ['EPIC-002', 'EPIC-003'],
            'estimated_months': 2,
            'story_points': 95
        },
        'EPIC-NFR': {
            'name': 'Non-Functional Requirements',
            'priority': 'P0',
            'phase': 8,
            'complexity': 'Very High',
            'risk': 'High',
            'dependencies': ['ALL'],
            'estimated_months': 3,
            'story_points': 168
        }
    }

# Initialize session state
if 'epic_data' not in st.session_state:
    st.session_state.epic_data = initialize_epic_data()

def calculate_phase_cost(phase_id):
    """Calculate detailed cost for a phase"""
    phase = PHASES[phase_id]
    resources = phase['resources']
    duration = phase['duration']
    hours_per_month = st.session_state.config['hours_per_month']
    
    onsite_cost = 0
    offshore_cost = 0
    
    # Calculate onsite costs
    for role, count in resources.get('onsite', {}).items():
        rate = st.session_state.config['hourly_rates']['onsite'].get(role, 100)
        onsite_cost += rate * count * hours_per_month * duration
    
    # Calculate offshore costs
    for role, count in resources.get('offshore', {}).items():
        rate = st.session_state.config['hourly_rates']['offshore'].get(role, 20)
        offshore_cost += rate * count * hours_per_month * duration
    
    return {
        'onsite': onsite_cost,
        'offshore': offshore_cost,
        'total': onsite_cost + offshore_cost,
        'duration': duration,
        'team_size': sum(resources.get('onsite', {}).values()) + sum(resources.get('offshore', {}).values())
    }

def calculate_total_program_cost():
    """Calculate total program cost with all components"""
    development_cost = sum(calculate_phase_cost(i)['total'] for i in range(9))
    
    # Infrastructure costs (monthly)
    infrastructure_monthly = {
        'Azure_AKS': 8000,
        'Azure_Storage': 2000,
        'Azure_Networking': 3000,
        'Monitoring': 2000,
        'Security_Tools': 3000,
        'Licenses': 5000
    }
    
    total_infra = sum(infrastructure_monthly.values()) * st.session_state.config['program_duration']
    
    # Additional costs
    additional_costs = {
        'Training': 50000,
        'Documentation': 30000,
        'Third_Party_Integrations': 100000,
        'Data_Migration_Tools': 75000,
        'Testing_Tools': 40000,
        'Consulting': 150000
    }
    
    subtotal = development_cost + total_infra + sum(additional_costs.values())
    contingency = subtotal * (st.session_state.config['contingency_percent'] / 100)
    
    return {
        'development': development_cost,
        'infrastructure': total_infra,
        'additional': sum(additional_costs.values()),
        'subtotal': subtotal,
        'contingency': contingency,
        'total': subtotal + contingency,
        'infrastructure_breakdown': infrastructure_monthly,
        'additional_breakdown': additional_costs
    }

def main():
    # Enhanced header with logo placeholder
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        st.title("🚀 SPLUS RTM Platform Modernization")
        st.markdown("**Enterprise Transportation Management System Transformation**")
    
    # Top-level navigation
    selected_page = st.sidebar.radio(
        "📍 Navigation",
        ["🏠 Executive Overview", "💰 Cost Analysis", "📊 Program Planning", 
         "📋 EPICs & Stories", "👥 Resource Management", "📈 Analytics & Reports",
         "⚙️ Configuration"]
    )
    
    # Info box
    with st.sidebar:
        st.info(f"""
        **Program Status**
        - Duration: {st.session_state.config['program_duration']} months
        - Phases: 9
        - EPICs: {len(st.session_state.epic_data)}
        - Total Points: {sum(e['story_points'] for e in st.session_state.epic_data.values())}
        """)
    
    if selected_page == "🏠 Executive Overview":
        show_executive_overview()
    elif selected_page == "💰 Cost Analysis":
        show_cost_analysis()
    elif selected_page == "📊 Program Planning":
        show_program_planning()
    elif selected_page == "📋 EPICs & Stories":
        show_epics_stories()
    elif selected_page == "👥 Resource Management":
        show_resource_management()
    elif selected_page == "📈 Analytics & Reports":
        show_analytics_reports()
    elif selected_page == "⚙️ Configuration":
        show_configuration()

def show_executive_overview():
    """Executive dashboard with key metrics"""
    st.header("🏠 Executive Overview")
    
    # Calculate metrics
    total_costs = calculate_total_program_cost()
    
    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Investment",
            f"${total_costs['total']:,.0f}",
            f"Incl. {st.session_state.config['contingency_percent']}% contingency"
        )
    
    with col2:
        st.metric(
            "Development Cost",
            f"${total_costs['development']:,.0f}",
            f"{(total_costs['development']/total_costs['total']*100):.0f}% of total"
        )
    
    with col3:
        monthly_burn = total_costs['total'] / st.session_state.config['program_duration']
        st.metric(
            "Monthly Burn Rate",
            f"${monthly_burn:,.0f}",
            "Average per month"
        )
    
    with col4:
        roi_annual = 5500000  # $5.5M annual benefit
        payback = total_costs['total'] / roi_annual * 12
        st.metric(
            "Payback Period",
            f"{payback:.1f} months",
            "Post go-live"
        )
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Phase Overview", "💵 Cost Breakdown", "⏱️ Timeline", "🎯 Benefits"])
    
    with tab1:
        # Phase overview chart
        phase_data = []
        for i in range(9):
            cost = calculate_phase_cost(i)
            phase_data.append({
                'Phase': f"Phase {i}",
                'Name': PHASES[i]['name'],
                'Cost': cost['total'],
                'Duration': PHASES[i]['duration'],
                'Team Size': cost['team_size']
            })
        
        df_phases = pd.DataFrame(phase_data)
        
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(df_phases, x='Phase', y='Cost', 
                        title='Cost by Phase',
                        hover_data=['Name', 'Duration', 'Team Size'])
            fig.update_traces(marker_color='lightblue')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.pie(df_phases, values='Duration', names='Name',
                        title='Duration Distribution (Months)')
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        # Cost breakdown
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Cost Components")
            cost_breakdown = {
                'Development': total_costs['development'],
                'Infrastructure': total_costs['infrastructure'],
                'Additional': total_costs['additional'],
                'Contingency': total_costs['contingency']
            }
            
            fig = go.Figure(data=[
                go.Bar(x=list(cost_breakdown.keys()), 
                      y=list(cost_breakdown.values()),
                      text=[f"${v:,.0f}" for v in cost_breakdown.values()],
                      textposition='auto',
                      marker_color=['blue', 'green', 'orange', 'red'])
            ])
            fig.update_layout(title="Cost Components Breakdown")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Monthly Infrastructure Costs")
            infra_df = pd.DataFrame([
                {'Component': k.replace('_', ' '), 'Monthly Cost': v}
                for k, v in total_costs['infrastructure_breakdown'].items()
            ])
            infra_df['Total (24 months)'] = infra_df['Monthly Cost'] * 24
            st.dataframe(infra_df, use_container_width=True, hide_index=True)
    
    with tab3:
        # Timeline visualization
        st.subheader("Program Timeline")
        
        timeline_data = []
        start_date = datetime(2024, 1, 1)
        
        for i in range(9):
            phase = PHASES[i]
            end_date = start_date + timedelta(days=phase['duration'] * 30)
            timeline_data.append({
                'Phase': f"Phase {i}: {phase['name']}",
                'Start': start_date,
                'End': end_date,
                'Duration': f"{phase['duration']} months"
            })
            start_date = end_date
        
        df_timeline = pd.DataFrame(timeline_data)
        
        fig = px.timeline(df_timeline, x_start="Start", x_end="End", y="Phase",
                         title="24-Month Implementation Timeline",
                         hover_data=['Duration'])
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        # Benefits realization
        st.subheader("Benefits Realization")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Annual Benefits")
            benefits = {
                'Operational Efficiency': 2000000,
                'Infrastructure Savings': 500000,
                'Support Cost Reduction': 300000,
                'Increased Revenue': 2500000,
                'Penalty Avoidance': 200000
            }
            
            for benefit, value in benefits.items():
                st.metric(benefit, f"${value:,.0f}")
        
        with col2:
            # ROI projection chart
            years = list(range(6))
            investment = total_costs['total']
            annual_benefit = sum(benefits.values())
            cumulative_benefit = [annual_benefit * i - investment for i in years]
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=years, y=cumulative_benefit,
                                    mode='lines+markers',
                                    name='Cumulative Benefit',
                                    line=dict(width=3)))
            fig.add_hline(y=0, line_dash="dash", line_color="red")
            fig.update_layout(title="ROI Projection (5 Years)",
                            xaxis_title="Years",
                            yaxis_title="Cumulative Benefit ($)")
            st.plotly_chart(fig, use_container_width=True)

def show_cost_analysis():
    """Detailed cost analysis page"""
    st.header("💰 Cost Analysis")
    
    # Contingency slider at the top
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        new_contingency = st.slider(
            "Adjust Contingency Percentage",
            min_value=10,
            max_value=30,
            value=st.session_state.config['contingency_percent'],
            step=5,
            help="Adjust contingency to see impact on total cost"
        )
        if new_contingency != st.session_state.config['contingency_percent']:
            st.session_state.config['contingency_percent'] = new_contingency
            st.rerun()
    
    # Tabs for different cost views
    tab1, tab2, tab3, tab4 = st.tabs(["Phase Costs", "Resource Costs", "Infrastructure", "TCO Analysis"])
    
    with tab1:
        st.subheader("Phase-by-Phase Cost Breakdown")
        
        phase_costs = []
        for i in range(9):
            cost = calculate_phase_cost(i)
            phase = PHASES[i]
            phase_costs.append({
                'Phase': i,
                'Name': phase['name'],
                'Duration (months)': phase['duration'],
                'Onsite Cost': cost['onsite'],
                'Offshore Cost': cost['offshore'],
                'Total Cost': cost['total'],
                'Team Size': cost['team_size'],
                'Cost/Month': cost['total'] / phase['duration'] if phase['duration'] > 0 else 0
            })
        
        df_phase_costs = pd.DataFrame(phase_costs)
        
        # Display editable dataframe
        st.dataframe(
            df_phase_costs.style.format({
                'Onsite Cost': '${:,.0f}',
                'Offshore Cost': '${:,.0f}',
                'Total Cost': '${:,.0f}',
                'Cost/Month': '${:,.0f}'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Visualizations
        col1, col2 = st.columns(2)
        
        with col1:
            fig = go.Figure()
            fig.add_trace(go.Bar(name='Onsite', x=df_phase_costs['Phase'], 
                               y=df_phase_costs['Onsite Cost']))
            fig.add_trace(go.Bar(name='Offshore', x=df_phase_costs['Phase'], 
                               y=df_phase_costs['Offshore Cost']))
            fig.update_layout(barmode='stack', title='Onsite vs Offshore Cost Distribution',
                            xaxis_title='Phase', yaxis_title='Cost ($)')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Cost efficiency metrics
            total_onsite = df_phase_costs['Onsite Cost'].sum()
            total_offshore = df_phase_costs['Offshore Cost'].sum()
            offshore_ratio = total_offshore / (total_onsite + total_offshore) * 100
            
            st.info(f"""
            **Cost Efficiency Metrics**
            - Total Onsite: ${total_onsite:,.0f}
            - Total Offshore: ${total_offshore:,.0f}
            - Offshore Ratio: {offshore_ratio:.1f}%
            - Blended Rate: ${(total_onsite + total_offshore) / (24 * 160 * 20):.0f}/hr
            """)
            
            # Phase cost trend
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df_phase_costs['Phase'], 
                                    y=df_phase_costs['Cost/Month'],
                                    mode='lines+markers',
                                    name='Monthly Burn Rate'))
            fig.update_layout(title='Monthly Burn Rate by Phase',
                            xaxis_title='Phase', yaxis_title='Cost/Month ($)')
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("Resource Cost Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Onsite Resource Rates")
            onsite_df = pd.DataFrame([
                {'Role': role, 'Hourly Rate': rate, 'Monthly Cost (160 hrs)': rate * 160}
                for role, rate in st.session_state.config['hourly_rates']['onsite'].items()
            ])
            st.dataframe(onsite_df, use_container_width=True, hide_index=True)
        
        with col2:
            st.markdown("### Offshore Resource Rates")
            offshore_df = pd.DataFrame([
                {'Role': role, 'Hourly Rate': rate, 'Monthly Cost (160 hrs)': rate * 160}
                for role, rate in st.session_state.config['hourly_rates']['offshore'].items()
            ])
            st.dataframe(offshore_df, use_container_width=True, hide_index=True)
        
        # Resource utilization chart
        st.subheader("Resource Utilization Across Phases")
        
        resource_data = []
        for i in range(9):
            phase = PHASES[i]
            onsite_count = sum(phase['resources'].get('onsite', {}).values())
            offshore_count = sum(phase['resources'].get('offshore', {}).values())
            resource_data.append({
                'Phase': f"Phase {i}",
                'Onsite': onsite_count,
                'Offshore': offshore_count
            })
        
        df_resources = pd.DataFrame(resource_data)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Onsite', x=df_resources['Phase'], y=df_resources['Onsite']))
        fig.add_trace(go.Bar(name='Offshore', x=df_resources['Phase'], y=df_resources['Offshore']))
        fig.update_layout(title='Team Size by Phase', barmode='group',
                         xaxis_title='Phase', yaxis_title='Number of Resources')
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.subheader("Infrastructure & Additional Costs")
        
        total_costs = calculate_total_program_cost()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Monthly Infrastructure Costs")
            for component, cost in total_costs['infrastructure_breakdown'].items():
                st.metric(component.replace('_', ' '), f"${cost:,.0f}/month")
            
            st.info(f"""
            **Infrastructure Summary**
            - Monthly Total: ${sum(total_costs['infrastructure_breakdown'].values()):,.0f}
            - 24-Month Total: ${total_costs['infrastructure']:,.0f}
            """)
        
        with col2:
            st.markdown("### One-Time Additional Costs")
            for component, cost in total_costs['additional_breakdown'].items():
                st.metric(component.replace('_', ' '), f"${cost:,.0f}")
            
            st.info(f"""
            **Additional Costs Total**
            - One-time Total: ${total_costs['additional']:,.0f}
            """)
    
    with tab4:
        st.subheader("Total Cost of Ownership (TCO)")
        
        total_costs = calculate_total_program_cost()
        
        # TCO breakdown
        st.markdown("### 24-Month TCO Breakdown")
        
        tco_data = {
            'Component': ['Development', 'Infrastructure', 'Additional', 'Contingency', 'TOTAL'],
            'Cost': [
                total_costs['development'],
                total_costs['infrastructure'],
                total_costs['additional'],
                total_costs['contingency'],
                total_costs['total']
            ],
            'Percentage': [
                total_costs['development'] / total_costs['total'] * 100,
                total_costs['infrastructure'] / total_costs['total'] * 100,
                total_costs['additional'] / total_costs['total'] * 100,
                total_costs['contingency'] / total_costs['total'] * 100,
                100
            ]
        }
        
        df_tco = pd.DataFrame(tco_data)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.dataframe(
                df_tco.style.format({
                    'Cost': '${:,.0f}',
                    'Percentage': '{:.1f}%'
                }),
                use_container_width=True,
                hide_index=True
            )
        
        with col2:
            st.metric("Total Investment", f"${total_costs['total']:,.0f}")
            st.metric("Per Month Average", f"${total_costs['total']/24:,.0f}")
            st.metric("Contingency Buffer", f"{st.session_state.config['contingency_percent']}%")
        
        # Cost comparison scenarios
        st.markdown("### Cost Scenarios Analysis")
        
        scenarios = []
        for contingency in [10, 15, 20, 25, 30]:
            scenario_cost = total_costs['subtotal'] * (1 + contingency/100)
            scenarios.append({
                'Contingency %': contingency,
                'Total Cost': scenario_cost,
                'Difference': scenario_cost - total_costs['total']
            })
        
        df_scenarios = pd.DataFrame(scenarios)
        
        fig = px.line(df_scenarios, x='Contingency %', y='Total Cost',
                     title='Total Cost vs Contingency Percentage',
                     markers=True)
        fig.update_traces(line=dict(width=3))
        st.plotly_chart(fig, use_container_width=True)

def show_program_planning():
    """Program planning and timeline management"""
    st.header("📊 Program Planning")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Roadmap", "Dependencies", "Milestones", "Risk Matrix"])
    
    with tab1:
        st.subheader("Implementation Roadmap")
        
        # Create detailed roadmap
        roadmap_data = []
        start_date = datetime(2024, 1, 1)
        
        for i in range(9):
            phase = PHASES[i]
            end_date = start_date + timedelta(days=phase['duration'] * 30)
            
            # Get EPICs in this phase
            phase_epics = [epic_id for epic_id, epic in st.session_state.epic_data.items() 
                          if epic['phase'] == i]
            
            roadmap_data.append({
                'Phase': f"Phase {i}",
                'Name': phase['name'],
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d'),
                'Duration': f"{phase['duration']} months",
                'EPICs': ', '.join(phase_epics[:3]) + ('...' if len(phase_epics) > 3 else ''),
                'Deliverables': ', '.join(phase['deliverables'][:3])
            })
            start_date = end_date
        
        df_roadmap = pd.DataFrame(roadmap_data)
        st.dataframe(df_roadmap, use_container_width=True, hide_index=True)
        
        # Gantt chart
        fig = go.Figure()
        
        for idx, row in df_roadmap.iterrows():
            fig.add_trace(go.Scatter(
                x=[pd.to_datetime(row['Start']), pd.to_datetime(row['End'])],
                y=[row['Phase'], row['Phase']],
                mode='lines',
                line=dict(width=20),
                name=row['Name'],
                hovertext=f"{row['Name']}<br>Duration: {row['Duration']}<br>EPICs: {row['EPICs']}"
            ))
        
        fig.update_layout(
            title="Program Gantt Chart",
            xaxis_title="Timeline",
            yaxis_title="Phase",
            height=500,
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("EPIC Dependencies")
        
        # Dependency matrix
        dependency_data = []
        for epic_id, epic in st.session_state.epic_data.items():
            deps = epic['dependencies'] if epic['dependencies'] else ['None']
            dependency_data.append({
                'EPIC': epic_id,
                'Name': epic['name'],
                'Phase': epic['phase'],
                'Dependencies': ', '.join(deps),
                'Complexity': epic['complexity'],
                'Risk': epic['risk']
            })
        
        df_deps = pd.DataFrame(dependency_data)
        st.dataframe(df_deps, use_container_width=True, hide_index=True)
        
        # Dependency visualization
        st.subheader("Dependency Graph")
        st.info("Complex dependencies between EPICs require careful sequencing and parallel execution where possible")
    
    with tab3:
        st.subheader("Key Milestones")
        
        milestones = [
            {'Month': 3, 'Milestone': 'Foundation Complete', 'Deliverable': 'Cloud infrastructure ready'},
            {'Month': 6, 'Milestone': 'Customer Portal Live', 'Deliverable': 'CFW modernized and deployed'},
            {'Month': 9, 'Milestone': 'Order System Live', 'Deliverable': 'Order processing operational'},
            {'Month': 12, 'Milestone': 'Inventory Integration', 'Deliverable': 'IMS fully integrated'},
            {'Month': 15, 'Milestone': 'Routing Engine Live', 'Deliverable': 'MORO integrated'},
            {'Month': 18, 'Milestone': 'Vendor Platform Ready', 'Deliverable': 'Vendor/Driver management live'},
            {'Month': 21, 'Milestone': 'Billing System Live', 'Deliverable': 'Complete billing automation'},
            {'Month': 24, 'Milestone': 'Full Production', 'Deliverable': 'Complete system cutover'}
        ]
        
        df_milestones = pd.DataFrame(milestones)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            fig = px.scatter(df_milestones, x='Month', y='Milestone', 
                           size=[100]*len(milestones),
                           hover_data=['Deliverable'],
                           title='Major Milestones')
            fig.update_traces(marker=dict(color='red'))
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.dataframe(df_milestones[['Month', 'Milestone']], 
                        use_container_width=True, hide_index=True)
    
    with tab4:
        st.subheader("Risk Assessment Matrix")
        
        risks = [
            {'Risk': 'IMS Integration Complexity', 'Impact': 'High', 'Probability': 'High', 'Score': 9,
             'Mitigation': 'Dedicated integration team, phased approach'},
            {'Risk': 'MORO Integration Delays', 'Impact': 'High', 'Probability': 'Medium', 'Score': 6,
             'Mitigation': 'TNT WebServices as fallback, early vendor engagement'},
            {'Risk': 'Data Migration Issues', 'Impact': 'High', 'Probability': 'Low', 'Score': 3,
             'Mitigation': 'Multiple dry runs, automated tools, parallel run'},
            {'Risk': 'User Adoption Resistance', 'Impact': 'Medium', 'Probability': 'High', 'Score': 6,
             'Mitigation': 'Comprehensive training, change management program'},
            {'Risk': 'Performance Degradation', 'Impact': 'High', 'Probability': 'Low', 'Score': 3,
             'Mitigation': 'Load testing, auto-scaling, performance optimization'},
            {'Risk': 'Security Vulnerabilities', 'Impact': 'High', 'Probability': 'Low', 'Score': 3,
             'Mitigation': 'Security scanning, penetration testing, code reviews'},
            {'Risk': 'B2B Volume Spike', 'Impact': 'Medium', 'Probability': 'Medium', 'Score': 4,
             'Mitigation': 'Elastic scaling, queue management, circuit breakers'}
        ]
        
        df_risks = pd.DataFrame(risks)
        
        # Risk matrix visualization
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.dataframe(df_risks[['Risk', 'Score']], 
                        use_container_width=True, hide_index=True)
        
        with col2:
            # Create risk heatmap
            impact_map = {'Low': 1, 'Medium': 2, 'High': 3}
            prob_map = {'Low': 1, 'Medium': 2, 'High': 3}
            
            df_risks['Impact_Score'] = df_risks['Impact'].map(impact_map)
            df_risks['Prob_Score'] = df_risks['Probability'].map(prob_map)
            
            fig = go.Figure(data=go.Scatter(
                x=df_risks['Prob_Score'],
                y=df_risks['Impact_Score'],
                mode='markers+text',
                marker=dict(
                    size=df_risks['Score'] * 10,
                    color=df_risks['Score'],
                    colorscale='RdYlGn_r',
                    showscale=True,
                    colorbar=dict(title="Risk Score")
                ),
                text=df_risks.index + 1,
                textposition="middle center",
                hovertext=df_risks['Risk']
            ))
            
            fig.update_layout(
                title="Risk Matrix",
                xaxis=dict(
                    title="Probability",
                    tickvals=[1, 2, 3],
                    ticktext=["Low", "Medium", "High"]
                ),
                yaxis=dict(
                    title="Impact",
                    tickvals=[1, 2, 3],
                    ticktext=["Low", "Medium", "High"]
                ),
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Risk details
        st.subheader("Risk Mitigation Strategies")
        for idx, risk in df_risks.iterrows():
            with st.expander(f"{idx+1}. {risk['Risk']} (Score: {risk['Score']})"):
                st.write(f"**Impact:** {risk['Impact']}")
                st.write(f"**Probability:** {risk['Probability']}")
                st.write(f"**Mitigation:** {risk['Mitigation']}")

def show_epics_stories():
    """EPIC and user story management"""
    st.header("📋 EPICs & User Stories")
    
    # Summary metrics
    total_points = sum(epic['story_points'] for epic in st.session_state.epic_data.values())
    total_months = sum(epic['estimated_months'] for epic in st.session_state.epic_data.values())
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total EPICs", len(st.session_state.epic_data))
    with col2:
        st.metric("Total Story Points", total_points)
    with col3:
        st.metric("Total Effort", f"{total_months} months")
    with col4:
        st.metric("Average Velocity", f"{total_points/24:.0f} pts/month")
    
    # EPIC management tabs
    tab1, tab2, tab3 = st.tabs(["EPIC Overview", "Complexity Analysis", "Story Distribution"])
    
    with tab1:
        st.subheader("EPIC Details")
        
        # Create EPIC dataframe
        epic_df = pd.DataFrame.from_dict(st.session_state.epic_data, orient='index')
        epic_df = epic_df.reset_index().rename(columns={'index': 'EPIC ID'})
        
        # Display editable dataframe
        edited_df = st.data_editor(
            epic_df,
            column_config={
                "priority": st.column_config.SelectboxColumn(
                    "Priority",
                    options=["P0", "P1", "P2"]
                ),
                "complexity": st.column_config.SelectboxColumn(
                    "Complexity",
                    options=["Low", "Medium", "High", "Very High"]
                ),
                "risk": st.column_config.SelectboxColumn(
                    "Risk",
                    options=["Low", "Medium", "High", "Very High"]
                ),
                "phase": st.column_config.NumberColumn(
                    "Phase",
                    min_value=0,
                    max_value=8
                )
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Update data if edited
        if st.button("Save EPIC Changes"):
            for idx, row in edited_df.iterrows():
                epic_id = row['EPIC ID']
                if epic_id in st.session_state.epic_data:
                    st.session_state.epic_data[epic_id].update(row.to_dict())
            st.success("Changes saved successfully!")
    
    with tab2:
        st.subheader("Complexity Analysis")
        
        # Complexity distribution
        complexity_counts = {}
        complexity_points = {}
        
        for epic in st.session_state.epic_data.values():
            comp = epic['complexity']
            complexity_counts[comp] = complexity_counts.get(comp, 0) + 1
            complexity_points[comp] = complexity_points.get(comp, 0) + epic['story_points']
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.pie(values=list(complexity_counts.values()),
                        names=list(complexity_counts.keys()),
                        title="EPICs by Complexity")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.bar(x=list(complexity_points.keys()),
                        y=list(complexity_points.values()),
                        title="Story Points by Complexity",
                        labels={'x': 'Complexity', 'y': 'Story Points'})
            st.plotly_chart(fig, use_container_width=True)
        
        # Risk vs Complexity matrix
        st.subheader("Risk-Complexity Matrix")
        
        risk_complexity_data = []
        risk_map = {'Low': 1, 'Medium': 2, 'High': 3, 'Very High': 4}
        comp_map = {'Low': 1, 'Medium': 2, 'High': 3, 'Very High': 4}
        
        for epic_id, epic in st.session_state.epic_data.items():
            risk_complexity_data.append({
                'EPIC': epic_id,
                'Name': epic['name'],
                'Risk_Score': risk_map.get(epic['risk'], 2),
                'Complexity_Score': comp_map.get(epic['complexity'], 2),
                'Points': epic['story_points']
            })
        
        df_risk_comp = pd.DataFrame(risk_complexity_data)
        
        fig = go.Figure(data=go.Scatter(
            x=df_risk_comp['Complexity_Score'],
            y=df_risk_comp['Risk_Score'],
            mode='markers+text',
            marker=dict(
                size=df_risk_comp['Points'] / 10,
                color=df_risk_comp['Points'],
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="Story Points")
            ),
            text=df_risk_comp['EPIC'],
            hovertext=df_risk_comp['Name']
        ))
        
        fig.update_layout(
            title="EPIC Risk vs Complexity",
            xaxis=dict(
                title="Complexity",
                tickvals=[1, 2, 3, 4],
                ticktext=["Low", "Medium", "High", "Very High"]
            ),
            yaxis=dict(
                title="Risk",
                tickvals=[1, 2, 3, 4],
                ticktext=["Low", "Medium", "High", "Very High"]
            ),
            height=500
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.subheader("Story Point Distribution")
        
        # Phase-wise story distribution
        phase_stories = {}
        for epic in st.session_state.epic_data.values():
            phase = epic['phase']
            phase_stories[phase] = phase_stories.get(phase, 0) + epic['story_points']
        
        # Create distribution chart
        phases = list(range(9))
        points = [phase_stories.get(i, 0) for i in phases]
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=[f"Phase {i}" for i in phases],
            y=points,
            text=points,
            textposition='auto',
            marker_color='lightcoral'
        ))
        
        fig.update_layout(
            title="Story Points Distribution by Phase",
            xaxis_title="Phase",
            yaxis_title="Story Points",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Velocity calculation
        st.subheader("Velocity Planning")
        
        team_size = st.slider("Average Team Size", 10, 30, 20)
        points_per_dev = st.slider("Points per Developer per Sprint (2 weeks)", 5, 15, 10)
        
        velocity_per_sprint = team_size * points_per_dev
        velocity_per_month = velocity_per_sprint * 2
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Sprint Velocity", f"{velocity_per_sprint} points")
        with col2:
            st.metric("Monthly Velocity", f"{velocity_per_month} points")
        with col3:
            sprints_needed = int(np.ceil(total_points / velocity_per_sprint))
            st.metric("Sprints Needed", sprints_needed)

def show_resource_management():
    """Resource planning and management"""
    st.header("👥 Resource Management")
    
    tab1, tab2, tab3 = st.tabs(["Team Composition", "Resource Planning", "Skill Matrix"])
    
    with tab1:
        st.subheader("Phase-wise Team Composition")
        
        selected_phase = st.selectbox(
            "Select Phase",
            [f"Phase {i}: {PHASES[i]['name']}" for i in range(9)]
        )
        phase_id = int(selected_phase.split(":")[0].split()[1])
        
        phase = PHASES[phase_id]
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Onsite Team")
            onsite_resources = phase['resources'].get('onsite', {})
            for role, count in onsite_resources.items():
                rate = st.session_state.config['hourly_rates']['onsite'].get(role, 100)
                monthly_cost = rate * count * 160
                st.write(f"**{role}**: {count} resource(s)")
                st.caption(f"Cost: ${monthly_cost:,.0f}/month @ ${rate}/hr")
        
        with col2:
            st.markdown("### Offshore Team")
            offshore_resources = phase['resources'].get('offshore', {})
            for role, count in offshore_resources.items():
                rate = st.session_state.config['hourly_rates']['offshore'].get(role, 20)
                monthly_cost = rate * count * 160
                st.write(f"**{role}**: {count} resource(s)")
                st.caption(f"Cost: ${monthly_cost:,.0f}/month @ ${rate}/hr")
        
        # Team summary
        phase_cost = calculate_phase_cost(phase_id)
        
        st.info(f"""
        **Phase {phase_id} Team Summary**
        - Total Team Size: {phase_cost['team_size']} resources
        - Onsite: {sum(onsite_resources.values())} resources
        - Offshore: {sum(offshore_resources.values())} resources
        - Monthly Cost: ${phase_cost['total']/phase['duration']:,.0f}
        - Total Phase Cost: ${phase_cost['total']:,.0f}
        """)
    
    with tab2:
        st.subheader("Resource Ramp-up Plan")
        
        # Create resource timeline
        resource_timeline = []
        for i in range(9):
            phase = PHASES[i]
            onsite_count = sum(phase['resources'].get('onsite', {}).values())
            offshore_count = sum(phase['resources'].get('offshore', {}).values())
            
            resource_timeline.append({
                'Phase': i,
                'Name': phase['name'],
                'Duration': phase['duration'],
                'Onsite': onsite_count,
                'Offshore': offshore_count,
                'Total': onsite_count + offshore_count
            })
        
        df_resources = pd.DataFrame(resource_timeline)
        
        # Resource ramp-up chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_resources['Phase'], y=df_resources['Onsite'],
                               mode='lines+markers', name='Onsite', line=dict(width=3)))
        fig.add_trace(go.Scatter(x=df_resources['Phase'], y=df_resources['Offshore'],
                               mode='lines+markers', name='Offshore', line=dict(width=3)))
        fig.add_trace(go.Scatter(x=df_resources['Phase'], y=df_resources['Total'],
                               mode='lines+markers', name='Total', line=dict(width=3, dash='dash')))
        
        fig.update_layout(
            title="Resource Ramp-up Plan",
            xaxis_title="Phase",
            yaxis_title="Number of Resources",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Resource allocation table
        st.subheader("Detailed Resource Allocation")
        st.dataframe(df_resources, use_container_width=True, hide_index=True)
    
    with tab3:
        st.subheader("Required Skills Matrix")
        
        skills = {
            'Microservices': ['Critical', 'Critical', 'High', 'High', 'Medium', 'Low'],
            'Cloud (Azure)': ['Critical', 'Critical', 'High', 'Medium', 'Medium', 'Medium'],
            'Java/Spring Boot': ['High', 'Critical', 'Critical', 'High', 'Medium', 'Low'],
            'Angular': ['Medium', 'High', 'Critical', 'High', 'Medium', 'Low'],
            'Integration': ['High', 'High', 'High', 'Critical', 'Critical', 'Medium'],
            'DevOps/CI/CD': ['Critical', 'High', 'Medium', 'Medium', 'Low', 'Critical'],
            'Domain Knowledge': ['Critical', 'High', 'High', 'High', 'High', 'Medium'],
            'Testing': ['Medium', 'Medium', 'High', 'High', 'Critical', 'Critical']
        }
        
        roles = ['Architect', 'Sr. Developer', 'Developer', 'Integration Spec', 'Tester', 'DevOps']
        
        df_skills = pd.DataFrame(skills, index=roles)
        
        # Create heatmap
        skill_map = {'Low': 1, 'Medium': 2, 'High': 3, 'Critical': 4}
        numeric_skills = df_skills.applymap(lambda x: skill_map.get(x, 0))
        
        fig = px.imshow(numeric_skills,
                       labels=dict(x="Skill", y="Role", color="Importance"),
                       color_continuous_scale="RdYlGn",
                       aspect="auto")
        
        fig.update_layout(title="Skills Requirements Matrix", height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        # Skills legend
        st.info("""
        **Skill Levels:**
        - **Critical**: Essential for role success
        - **High**: Very important, significant impact
        - **Medium**: Important, moderate impact
        - **Low**: Nice to have, minimal impact
        """)

def show_analytics_reports():
    """Analytics and reporting section"""
    st.header("📈 Analytics & Reports")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Executive Report", "Cost Report", "Progress Report", "Export Data"])
    
    with tab1:
        st.subheader("Executive Summary Report")
        
        total_costs = calculate_total_program_cost()
        total_points = sum(epic['story_points'] for epic in st.session_state.epic_data.values())
        
        report = f"""
        # SPLUS RTM MODERNIZATION - EXECUTIVE REPORT
        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
        
        ## Program Overview
        - **Duration:** {st.session_state.config['program_duration']} months
        - **Total Investment:** ${total_costs['total']:,.0f}
        - **Development Cost:** ${total_costs['development']:,.0f}
        - **Infrastructure:** ${total_costs['infrastructure']:,.0f}
        - **Contingency:** {st.session_state.config['contingency_percent']}%
        
        ## Scope
        - **EPICs:** {len(st.session_state.epic_data)}
        - **Total Story Points:** {total_points}
        - **Average Velocity Required:** {total_points/24:.0f} points/month
        
        ## Key Deliverables by Phase
        """
        
        for i in range(9):
            phase = PHASES[i]
            cost = calculate_phase_cost(i)
            report += f"""
        ### Phase {i}: {phase['name']} ({phase['duration']} months)
        - Cost: ${cost['total']:,.0f}
        - Team Size: {cost['team_size']} resources
        - Deliverables: {', '.join(phase['deliverables'][:3])}
        """
        
        st.text_area("Report Preview", report, height=400)
        
        st.download_button(
            label="Download Executive Report",
            data=report,
            file_name=f"RTM_Executive_Report_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain"
        )
    
    with tab2:
        st.subheader("Detailed Cost Report")
        
        # Create comprehensive cost report
        cost_details = []
        for i in range(9):
            phase = PHASES[i]
            cost = calculate_phase_cost(i)
            cost_details.append({
                'Phase': i,
                'Name': phase['name'],
                'Duration': phase['duration'],
                'Onsite Cost': cost['onsite'],
                'Offshore Cost': cost['offshore'],
                'Total Cost': cost['total'],
                'Cost per Month': cost['total'] / phase['duration'] if phase['duration'] > 0 else 0
            })
        
        df_cost_report = pd.DataFrame(cost_details)
        
        # Add totals row
        totals = {
            'Phase': 'TOTAL',
            'Name': 'All Phases',
            'Duration': sum(p['duration'] for p in PHASES.values()),
            'Onsite Cost': df_cost_report['Onsite Cost'].sum(),
            'Offshore Cost': df_cost_report['Offshore Cost'].sum(),
            'Total Cost': df_cost_report['Total Cost'].sum(),
            'Cost per Month': df_cost_report['Total Cost'].sum() / 24
        }
        
        df_with_total = pd.concat([df_cost_report, pd.DataFrame([totals])], ignore_index=True)
        
        st.dataframe(
            df_with_total.style.format({
                'Onsite Cost': '${:,.0f}',
                'Offshore Cost': '${:,.0f}',
                'Total Cost': '${:,.0f}',
                'Cost per Month': '${:,.0f}'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Download cost report
        csv = df_with_total.to_csv(index=False)
        st.download_button(
            label="Download Cost Report (CSV)",
            data=csv,
            file_name=f"RTM_Cost_Report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    with tab3:
        st.subheader("Progress Tracking Report")
        
        # Simulated progress data
        current_month = st.slider("Current Month", 0, 24, 6)
        
        progress_data = []
        for i in range(9):
            phase = PHASES[i]
            # Calculate phase timeline
            phase_start = sum(PHASES[j]['duration'] for j in range(i))
            phase_end = phase_start + phase['duration']
            
            if current_month >= phase_end:
                progress = 100
                status = "Completed"
            elif current_month > phase_start:
                progress = ((current_month - phase_start) / phase['duration']) * 100
                status = "In Progress"
            else:
                progress = 0
                status = "Not Started"
            
            progress_data.append({
                'Phase': f"Phase {i}",
                'Name': phase['name'],
                'Status': status,
                'Progress %': progress,
                'Start Month': phase_start,
                'End Month': phase_end
            })
        
        df_progress = pd.DataFrame(progress_data)
        
        # Progress visualization
        fig = go.Figure()
        
        colors = {'Completed': 'green', 'In Progress': 'yellow', 'Not Started': 'gray'}
        
        for idx, row in df_progress.iterrows():
            fig.add_trace(go.Bar(
                x=[row['Progress %']],
                y=[row['Phase']],
                orientation='h',
                name=row['Name'],
                marker_color=colors[row['Status']],
                showlegend=False,
                hovertext=f"{row['Name']}: {row['Status']} ({row['Progress %']:.0f}%)"
            ))
        
        fig.update_layout(
            title=f"Program Progress - Month {current_month}",
            xaxis_title="Progress %",
            yaxis_title="Phase",
            xaxis=dict(range=[0, 100]),
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Progress table
        st.dataframe(
            df_progress.style.format({'Progress %': '{:.1f}%'}),
            use_container_width=True,
            hide_index=True
        )
    
    with tab4:
        st.subheader("Export Program Data")
        
        st.info("Export complete program data for external analysis")
        
        # Prepare export data
        export_data = {
            'program_config': st.session_state.config,
            'phases': PHASES,
            'epics': st.session_state.epic_data,
            'costs': calculate_total_program_cost()
        }
        
        # JSON export
        json_str = json.dumps(export_data, indent=2, default=str)
        
        st.download_button(
            label="Download Complete Data (JSON)",
            data=json_str,
            file_name=f"RTM_Program_Data_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json"
        )
        
        st.success("Data ready for export. Click the button above to download.")

def show_configuration():
    """Configuration settings"""
    st.header("⚙️ Configuration")
    
    tab1, tab2, tab3 = st.tabs(["Program Settings", "Resource Rates", "Risk Parameters"])
    
    with tab1:
        st.subheader("Program Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.config['program_duration'] = st.number_input(
                "Program Duration (months)",
                min_value=18,
                max_value=36,
                value=st.session_state.config['program_duration']
            )
            
            st.session_state.config['contingency_percent'] = st.number_input(
                "Contingency Percentage",
                min_value=10,
                max_value=30,
                value=st.session_state.config['contingency_percent']
            )
        
        with col2:
            st.session_state.config['hours_per_month'] = st.number_input(
                "Working Hours per Month",
                min_value=140,
                max_value=180,
                value=st.session_state.config['hours_per_month']
            )
            
            st.session_state.config['buffer_percent'] = st.number_input(
                "Risk Buffer Percentage",
                min_value=5,
                max_value=20,
                value=st.session_state.config['buffer_percent']
            )
        
        if st.button("Save Configuration"):
            st.success("Configuration saved successfully!")
            st.rerun()
    
    with tab2:
        st.subheader("Resource Rate Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Onsite Rates ($/hr)")
            for role in st.session_state.config['hourly_rates']['onsite']:
                st.session_state.config['hourly_rates']['onsite'][role] = st.number_input(
                    role,
                    min_value=50,
                    max_value=200,
                    value=st.session_state.config['hourly_rates']['onsite'][role],
                    key=f"onsite_{role}_config"
                )
        
        with col2:
            st.markdown("### Offshore Rates ($/hr)")
            for role in st.session_state.config['hourly_rates']['offshore']:
                st.session_state.config['hourly_rates']['offshore'][role] = st.number_input(
                    role,
                    min_value=10,
                    max_value=50,
                    value=st.session_state.config['hourly_rates']['offshore'][role],
                    key=f"offshore_{role}_config"
                )
        
        if st.button("Update Rates"):
            st.success("Rates updated successfully!")
            st.rerun()
    
    with tab3:
        st.subheader("Risk Parameters")
        
        st.info("Configure risk thresholds and mitigation strategies")
        
        risk_params = {
            'High Risk Threshold': st.slider("High Risk Score Threshold", 6, 10, 8),
            'Medium Risk Threshold': st.slider("Medium Risk Score Threshold", 3, 6, 5),
            'Mitigation Budget %': st.slider("Risk Mitigation Budget (%)", 5, 15, 10),
            'Review Frequency': st.selectbox("Risk Review Frequency", 
                                           ["Weekly", "Bi-weekly", "Monthly"])
        }
        
        st.write("### Current Risk Parameters:")
        for param, value in risk_params.items():
            st.write(f"- **{param}:** {value}")

if __name__ == "__main__":
    main()
