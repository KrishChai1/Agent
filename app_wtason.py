import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(
    page_title="UPS-IBM Watson Strategic Implementation Platform",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 48px;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 30px;
        font-weight: bold;
    }
    .sub-header {
        font-size: 24px;
        color: #3730A3;
        margin-top: 20px;
        margin-bottom: 10px;
        font-weight: bold;
    }
    .metric-card {
        background-color: #F3F4F6;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    .info-box {
        background-color: #EBF8FF;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #3182CE;
        margin-bottom: 15px;
    }
    .warning-box {
        background-color: #FFF5F5;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #E53E3E;
        margin-bottom: 15px;
    }
    .success-box {
        background-color: #F0FDF4;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #38A169;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<h1 class="main-header">🚚 UPS-IBM Watson Strategic Implementation Platform</h1>', unsafe_allow_html=True)
st.markdown("### Comprehensive Analysis for TechM Leadership - UPS AI Transformation Journey")

# Sidebar
with st.sidebar:
    st.image("https://via.placeholder.com/300x100/6B3410/FFFFFF?text=UPS+%2B+IBM+Watson", width=300)
    st.markdown("### 🎯 Quick Navigation")
    selected_tab = st.selectbox(
        "Select Analysis Section",
        ["Executive Dashboard", "IBM Watson Products", "UPS Use Cases", "Training Curriculum", 
         "Governance Framework", "IBM Requirements", "Implementation Roadmap", "ROI Analysis"]
    )
    
    st.markdown("---")
    st.markdown("### 📊 Key Metrics")
    st.metric("Expected ROI", "$300M+/year", "↑ Based on UPS ORION")
    st.metric("Implementation Timeline", "12 Months", "Phased Approach")
    st.metric("Training Duration", "10 Weeks", "Per Team")

# Tab Content
if selected_tab == "Executive Dashboard":
    st.markdown('<h2 class="sub-header">📊 Executive Dashboard</h2>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Watson Products", "15+", help="Complete portfolio of AI solutions")
    with col2:
        st.metric("Identified Use Cases", "50+", help="Across all UPS operations")
    with col3:
        st.metric("Expected Efficiency Gain", "30-40%", help="Based on industry benchmarks")
    with col4:
        st.metric("Carbon Reduction", "100K MT/year", help="Environmental impact")
    
    # Key Success Factors
    st.markdown("### 🎯 Critical Success Factors for UPS-Watson Implementation")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="success-box">
        <h4>✅ UPS Current AI Strengths</h4>
        <ul>
        <li><b>ORION System:</b> Saves 100M miles annually</li>
        <li><b>EDGE Platform:</b> $200-300M annual savings</li>
        <li><b>MeRA Tool:</b> 50% reduction in email resolution time</li>
        <li><b>LAL Platform:</b> 20-language support</li>
        <li><b>Data Scale:</b> 1B+ data points daily</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="info-box">
        <h4>🚀 Watson Enhancement Opportunities</h4>
        <ul>
        <li><b>Governance:</b> EU AI Act compliance automation</li>
        <li><b>GenAI Scale:</b> Enterprise-wide deployment</li>
        <li><b>Code Modernization:</b> Legacy COBOL systems</li>
        <li><b>Voice AI:</b> Driver assistance systems</li>
        <li><b>Predictive Analytics:</b> Advanced demand forecasting</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Strategic Alignment Chart
    st.markdown("### 🎯 Strategic Alignment: UPS Goals vs Watson Capabilities")
    
    alignment_data = {
        'UPS Strategic Goal': [
            'Carbon Neutral by 2050',
            'Customer Experience Excellence',
            'Operational Efficiency',
            'Global Smart Logistics Network',
            'Employee Empowerment'
        ],
        'Watson Solution': [
            'watsonx.ai for route optimization',
            'Watson Assistant for 24/7 support',
            'Watson Orchestrate for automation',
            'watsonx.data for unified platform',
            'Watson Code Assistant for developers'
        ],
        'Impact Score': [95, 90, 92, 88, 85]
    }
    
    fig = px.bar(alignment_data, x='Impact Score', y='UPS Strategic Goal', 
                 orientation='h', color='Impact Score',
                 color_continuous_scale='viridis',
                 title='Strategic Alignment Score (0-100)')
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

elif selected_tab == "IBM Watson Products":
    st.markdown('<h2 class="sub-header">🤖 Complete IBM Watson Product Portfolio</h2>', unsafe_allow_html=True)
    
    # Product categories
    product_categories = {
        "Core AI Platform": ["watsonx.ai", "watsonx.data", "watsonx.governance"],
        "Automation & Assistants": ["Watson Assistant", "Watson Orchestrate", "Watson Code Assistant"],
        "Language & Speech": ["Speech to Text", "Text to Speech", "Natural Language Understanding", "NLP Library"],
        "Analytics & Discovery": ["Watson Discovery", "Watson Studio"]
    }
    
    # Detailed product information - FIXED: Removed extra bracket
    product_details = {
        "watsonx.ai": {
            "description": "Next-generation enterprise studio for AI builders to train, validate, tune, and deploy AI models",
            "key_features": [
                "Foundation model library with IBM Granite models",
                "Support for open-source models (Hugging Face integration)",
                "Visual modeling and AutoML capabilities",
                "Python/R notebooks and IDE integration",
                "Model versioning and deployment management",
                "Synthetic data generation",
                "Cost-optimized inference",
                "Multi-cloud deployment (AWS, Azure, IBM Cloud)"
            ],
            "technical_specs": {
                "Models": "Granite series, Llama, FLAN, custom models",
                "Languages": "Python, R, SQL",
                "Deployment": "REST API, Batch, Streaming",
                "Scale": "Up to 1M+ predictions/day"
            },
            "pricing": "Starting at $0.00006 per 1K tokens",
            "ups_relevance": "Critical for route optimization, demand forecasting, and predictive maintenance"
        },
        "watsonx.data": {
            "description": "Hybrid, open data lakehouse platform to power AI and analytics with all your data, anywhere",
            "key_features": [
                "Unified control plane for all data types",
                "Multi-engine support (Spark, Presto, Presto C++)",
                "Automated data preparation and enrichment",
                "Document lineage tracking",
                "Cost optimization through fit-for-purpose engines",
                "Integration with 100+ data sources",
                "Real-time streaming capabilities",
                "Built-in data governance"
            ],
            "technical_specs": {
                "Storage": "S3 compatible, HDFS, Cloud native",
                "Processing": "Batch, streaming, real-time",
                "Formats": "Parquet, ORC, Avro, JSON, CSV",
                "Scale": "Petabyte-scale processing"
            },
            "pricing": "50% less than traditional data warehouses",
            "ups_relevance": "Essential for consolidating logistics data from 220 countries"
        },
        "watsonx.governance": {
            "description": "End-to-end AI governance toolkit for managing risk, compliance, and ethics",
            "key_features": [
                "Automated AI lifecycle workflows",
                "Real-time model monitoring and alerts",
                "Bias detection and mitigation",
                "Drift detection and model decay tracking",
                "Compliance accelerators (EU AI Act, ISO 42001)",
                "Multi-model governance (any platform)",
                "Audit trail and explainability",
                "Risk scorecards and dashboards"
            ],
            "technical_specs": {
                "Integrations": "SageMaker, Azure ML, Google Vertex",
                "Compliance": "EU AI Act, GDPR, CCPA, SOX",
                "Monitoring": "Real-time, batch evaluation",
                "Scale": "Manage 1000+ models"
            },
            "pricing": "$0.60 per resource unit (Essentials tier)",
            "ups_relevance": "Mandatory for regulatory compliance in 220 countries"
        },
        "Watson Assistant": {
            "description": "Enterprise conversational AI platform for building intelligent virtual assistants",
            "key_features": [
                "No-code conversation builder",
                "Large Language Model integration",
                "Multi-channel deployment (web, mobile, voice)",
                "13+ language support",
                "Actions-based dialog system",
                "Integration with 100+ enterprise apps",
                "Voice capabilities with STT/TTS",
                "Analytics and insights dashboard"
            ],
            "technical_specs": {
                "Channels": "Web, Mobile, SMS, Voice, Slack, Teams",
                "Languages": "13 languages with dialect support",
                "Integrations": "Salesforce, SAP, ServiceNow",
                "Scale": "10M+ messages/month"
            },
            "pricing": "Lite (free), Plus ($140/month), Enterprise (custom)",
            "ups_relevance": "Powers UPS chatbot handling millions of tracking queries"
        },
        "Watson Orchestrate": {
            "description": "AI-powered automation solution for complex business workflows",
            "key_features": [
                "Low-code agent builder",
                "Pre-built agent catalog",
                "Multi-agent collaboration",
                "100+ app integrations",
                "Natural language automation",
                "Process mining capabilities",
                "Role-based access control",
                "Analytics and reporting"
            ],
            "technical_specs": {
                "Agents": "Sales, HR, Procurement, Customer Service",
                "Integrations": "SAP, Workday, Salesforce, Office 365",
                "Deployment": "Cloud, Hybrid",
                "Scale": "10K+ automated workflows"
            },
            "pricing": "Starting at $500/month",
            "ups_relevance": "Automates supply chain and back-office processes"
        },
        "Watson Code Assistant": {
            "description": "AI-powered code generation and modernization tool suite",
            "key_features": [
                "Natural language to code generation",
                "Code explanation and documentation",
                "Legacy code modernization (COBOL to Java)",
                "Unit test generation",
                "Code review and optimization",
                "IDE integration (VS Code, Eclipse)",
                "IP indemnification",
                "Multiple language support"
            ],
            "variants": {
                "For Z": "Mainframe modernization",
                "For Red Hat Ansible": "IT automation",
                "For IBM i": "RPG programming"
            },
            "pricing": "30-day free trial, then usage-based",
            "ups_relevance": "Critical for modernizing UPS legacy tracking systems"
        },
        "Watson Discovery": {
            "description": "AI-powered intelligent document understanding and search",
            "key_features": [
                "Smart Document Understanding (SDU)",
                "Advanced NLP enrichments",
                "Pattern and anomaly detection",
                "Custom model training",
                "Relevancy training",
                "OCR capabilities",
                "100+ file format support",
                "Faceted search"
            ],
            "technical_specs": {
                "Documents": "Up to 100M documents",
                "Formats": "PDF, Word, HTML, JSON, CSV",
                "Languages": "50+ languages",
                "APIs": "REST, SDKs for major languages"
            },
            "pricing": "Lite (free), Advanced ($500/month)",
            "ups_relevance": "Processes shipping documents and contracts"
        },
        "Speech to Text": {
            "description": "Real-time speech transcription service with industry-leading accuracy",
            "key_features": [
                "Real-time transcription",
                "20+ language support",
                "Custom acoustic model training",
                "Speaker diarization",
                "Profanity filtering",
                "Custom vocabulary",
                "Noise handling",
                "Multiple audio format support"
            ],
            "technical_specs": {
                "Accuracy": "95%+ for clear audio",
                "Latency": "<200ms real-time",
                "Formats": "MP3, WAV, FLAC, OGG",
                "Concurrent": "Unlimited (Premium)"
            },
            "pricing": "Lite (free), Plus, Premium (unlimited)",
            "ups_relevance": "Essential for driver voice commands and call centers"
        }
    }
    
    # Display product categories
    for category, products in product_categories.items():
        st.markdown(f"### 📦 {category}")
        
        for product in products:
            with st.expander(f"**{product}** - Click for detailed information"):
                if product in product_details:
                    details = product_details[product]
                    
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"**Description:** {details['description']}")
                        
                        st.markdown("**Key Features:**")
                        for feature in details['key_features']:
                            st.markdown(f"• {feature}")
                    
                    with col2:
                        if 'technical_specs' in details:
                            st.markdown("**Technical Specifications:**")
                            for spec, value in details['technical_specs'].items():
                                st.markdown(f"**{spec}:** {value}")
                        
                        if 'pricing' in details:
                            st.markdown(f"**Pricing:** {details['pricing']}")
                        
                        if 'ups_relevance' in details:
                            st.markdown(f"**UPS Relevance:** _{details['ups_relevance']}_")

elif selected_tab == "UPS Use Cases":
    st.markdown('<h2 class="sub-header">🎯 UPS-Specific Watson Use Cases</h2>', unsafe_allow_html=True)
    
    # Use case categories with detailed implementation
    use_case_categories = {
        "📦 Package Operations": {
            "Intelligent Route Optimization Enhancement": {
                "current_state": "ORION saves 100M miles/year",
                "watson_solution": "watsonx.ai + watsonx.data",
                "implementation": [
                    "Real-time traffic and weather integration",
                    "Dynamic re-routing based on package priorities",
                    "Multi-modal transportation optimization",
                    "Driver preference learning algorithms"
                ],
                "expected_impact": "Additional 30% efficiency gain",
                "roi": "$150M annual savings"
            },
            "Predictive Package Volume Forecasting": {
                "current_state": "Basic seasonal predictions",
                "watson_solution": "watsonx.ai foundation models",
                "implementation": [
                    "Social media trend analysis",
                    "Economic indicator integration",
                    "Weather pattern correlation",
                    "Event-based surge prediction"
                ],
                "expected_impact": "85% forecast accuracy",
                "roi": "$75M in capacity optimization"
            },
            "Automated Damage Detection": {
                "current_state": "Manual inspection",
                "watson_solution": "Watson Visual Recognition + AI",
                "implementation": [
                    "Computer vision at sorting facilities",
                    "Real-time damage classification",
                    "Automated claim processing",
                    "Root cause analysis"
                ],
                "expected_impact": "90% detection accuracy",
                "roi": "$50M in reduced claims"
            }
        },
        "🤝 Customer Experience": {
            "Omnichannel Virtual Assistant": {
                "current_state": "Basic chatbot with 60% resolution",
                "watson_solution": "Watson Assistant + Discovery",
                "implementation": [
                    "Natural language understanding for complex queries",
                    "Proactive shipment notifications",
                    "Multi-language support (50+ languages)",
                    "Voice-enabled tracking"
                ],
                "expected_impact": "95% first-contact resolution",
                "roi": "$100M in support cost savings"
            },
            "Predictive Customer Service": {
                "current_state": "Reactive support model",
                "watson_solution": "watsonx.ai + Watson Assistant",
                "implementation": [
                    "Anticipate delivery issues before customer contact",
                    "Automated compensation offers",
                    "Personalized communication preferences",
                    "Sentiment analysis and escalation"
                ],
                "expected_impact": "40% reduction in complaints",
                "roi": "$60M in retention value"
            }
        },
        "🚛 Fleet & Logistics": {
            "Predictive Maintenance 2.0": {
                "current_state": "Schedule-based maintenance",
                "watson_solution": "watsonx.ai + IoT integration",
                "implementation": [
                    "Real-time vehicle telemetry analysis",
                    "Component failure prediction",
                    "Optimal maintenance scheduling",
                    "Parts inventory optimization"
                ],
                "expected_impact": "70% reduction in breakdowns",
                "roi": "$80M in reduced downtime"
            },
            "Driver Performance & Safety AI": {
                "current_state": "Basic telematics monitoring",
                "watson_solution": "watsonx.ai + Speech to Text",
                "implementation": [
                    "Real-time driver coaching via voice AI",
                    "Fatigue detection algorithms",
                    "Route-specific safety recommendations",
                    "Gamified performance improvement"
                ],
                "expected_impact": "50% reduction in accidents",
                "roi": "$120M in safety savings"
            }
        },
        "📊 Supply Chain Intelligence": {
            "End-to-End Visibility Platform": {
                "current_state": "Fragmented tracking systems",
                "watson_solution": "watsonx.data + Discovery",
                "implementation": [
                    "Unified data lakehouse for all shipments",
                    "Real-time exception handling",
                    "Predictive delay notifications",
                    "Blockchain integration for transparency"
                ],
                "expected_impact": "99.9% shipment visibility",
                "roi": "$90M in efficiency gains"
            },
            "Dynamic Capacity Planning": {
                "current_state": "Weekly manual planning",
                "watson_solution": "watsonx.ai + Orchestrate",
                "implementation": [
                    "AI-driven capacity allocation",
                    "Automated staff scheduling",
                    "Peak season optimization",
                    "Cross-facility load balancing"
                ],
                "expected_impact": "95% capacity utilization",
                "roi": "$110M in operational savings"
            },
            "Supply Chain Risk Management": {
                "current_state": "Reactive risk response",
                "watson_solution": "watsonx.ai + Discovery",
                "implementation": [
                    "Global event monitoring and impact analysis",
                    "Supplier risk scoring",
                    "Automated compliance checking",
                    "Predictive disruption modeling",
                    "Alternative route planning"
                ],
                "expected_impact": "60% faster risk response",
                "roi": "$100M in avoided disruptions"
            },
            "Financial Process Automation": {
                "current_state": "Manual invoice processing",
                "watson_solution": "Watson Orchestrate + Discovery",
                "implementation": [
                    "Automated invoice extraction and validation",
                    "Intelligent payment reconciliation",
                    "Fraud detection and prevention",
                    "Multi-currency optimization"
                ],
                "expected_impact": "90% automation rate",
                "roi": "$40M in processing savings"
            }
        },
        "💻 IT Modernization": {
            "Legacy System Transformation": {
                "current_state": "COBOL-based tracking systems",
                "watson_solution": "Watson Code Assistant for Z",
                "implementation": [
                    "Automated COBOL to Java conversion",
                    "API wrapper generation",
                    "Microservices architecture migration",
                    "Continuous modernization pipeline"
                ],
                "expected_impact": "70% faster development",
                "roi": "$60M in IT efficiency"
            },
            "Intelligent IT Operations": {
                "current_state": "Traditional monitoring",
                "watson_solution": "Watson AIOps + Orchestrate",
                "implementation": [
                    "Predictive incident prevention",
                    "Automated root cause analysis",
                    "Self-healing systems",
                    "Capacity planning AI"
                ],
                "expected_impact": "50% reduction in incidents",
                "roi": "$30M in IT cost savings"
            }
        },
        "🌱 Sustainability": {
            "Carbon Footprint Optimization": {
                "current_state": "Basic emissions tracking",
                "watson_solution": "watsonx.ai + watsonx.data",
                "implementation": [
                    "Real-time carbon calculation per package",
                    "Alternative fuel route optimization",
                    "Customer carbon offset options",
                    "Sustainability reporting automation"
                ],
                "expected_impact": "25% additional carbon reduction",
                "roi": "Support 2050 carbon neutral goal"
            },
            "Green Logistics Intelligence": {
                "current_state": "40% alternative fuel target by 2025",
                "watson_solution": "Watson AI suite",
                "implementation": [
                    "EV fleet optimization algorithms",
                    "Solar panel placement optimization",
                    "Packaging waste reduction AI",
                    "Circular economy modeling"
                ],
                "expected_impact": "Accelerate sustainability goals by 2 years",
                "roi": "$200M in sustainability incentives"
            }
        }
    }
    
    # Display use cases with detailed implementation plans
    for category, use_cases in use_case_categories.items():
        st.markdown(f"### {category}")
        
        for use_case_name, details in use_cases.items():
            with st.expander(f"**{use_case_name}**"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Current State:** {details['current_state']}")
                    st.markdown(f"**Watson Solution:** {details['watson_solution']}")
                    
                    st.markdown("**Implementation Steps:**")
                    for i, step in enumerate(details['implementation'], 1):
                        st.markdown(f"{i}. {step}")
                
                with col2:
                    st.markdown(f"**Expected Impact:**")
                    st.info(details['expected_impact'])
                    
                    st.markdown(f"**ROI Estimate:**")
                    st.success(details['roi'])
    
    # Use Case Priority Matrix
    st.markdown("### 📊 Use Case Priority Matrix")
    
    priority_data = {
        'Use Case': [
            'Route Optimization Enhancement',
            'Omnichannel Virtual Assistant', 
            'Supply Chain Risk Management',
            'Legacy System Transformation',
            'Carbon Footprint Optimization',
            'Predictive Maintenance',
            'Financial Process Automation'
        ],
        'Business Impact': [95, 90, 88, 85, 82, 80, 78],
        'Implementation Complexity': [60, 70, 75, 90, 65, 70, 60],
        'Time to Value (months)': [3, 4, 6, 12, 6, 5, 4]
    }
    
    fig = px.scatter(priority_data, 
                     x='Implementation Complexity', 
                     y='Business Impact',
                     size='Time to Value (months)',
                     color='Business Impact',
                     hover_data=['Use Case'],
                     title='Use Case Prioritization Matrix',
                     labels={'Business Impact': 'Business Impact Score',
                             'Implementation Complexity': 'Implementation Complexity Score'})
    
    # Add quadrant lines
    fig.add_hline(y=85, line_dash="dash", line_color="gray")
    fig.add_vline(x=75, line_dash="dash", line_color="gray")
    
    # Add quadrant labels
    fig.add_annotation(x=50, y=92, text="Quick Wins", showarrow=False, font=dict(size=12, color="green"))
    fig.add_annotation(x=85, y=92, text="Strategic Initiatives", showarrow=False, font=dict(size=12, color="blue"))
    fig.add_annotation(x=50, y=78, text="Fill Ins", showarrow=False, font=dict(size=12, color="orange"))
    fig.add_annotation(x=85, y=78, text="Nice to Have", showarrow=False, font=dict(size=12, color="red"))
    
    st.plotly_chart(fig, use_container_width=True)

elif selected_tab == "Training Curriculum":
    st.markdown('<h2 class="sub-header">🎓 Comprehensive Training Curriculum for TechM Teams</h2>', unsafe_allow_html=True)
    
    # Training tracks
    training_tracks = {
        "Executive Track": {
            "duration": "2 days",
            "audience": "C-level, VPs, Directors",
            "modules": [
                {
                    "title": "AI Strategy & Business Transformation",
                    "duration": "4 hours",
                    "topics": [
                        "AI landscape and Watson ecosystem overview",
                        "Business case development and ROI modeling",
                        "Change management for AI adoption",
                        "Governance and ethical AI principles"
                    ]
                },
                {
                    "title": "Watson for Business Leaders",
                    "duration": "4 hours",
                    "topics": [
                        "Strategic use cases across UPS operations",
                        "Competitive advantage through AI",
                        "Risk management and compliance",
                        "Building an AI-first culture"
                    ]
                },
                {
                    "title": "Implementation Strategy Workshop",
                    "duration": "8 hours",
                    "topics": [
                        "Roadmap development",
                        "Resource allocation",
                        "Success metrics definition",
                        "Stakeholder alignment"
                    ]
                }
            ]
        },
        "Technical Track": {
            "duration": "10 weeks",
            "audience": "Developers, Data Scientists, Engineers",
            "modules": [
                {
                    "title": "Week 1-2: Watson Foundations",
                    "duration": "80 hours",
                    "topics": [
                        "Watson architecture and components",
                        "Setting up development environments",
                        "API fundamentals and authentication",
                        "Basic model deployment"
                    ],
                    "labs": [
                        "Deploy your first Watson model",
                        "Build a simple chatbot",
                        "Connect to UPS data sources"
                    ]
                },
                {
                    "title": "Week 3-4: watsonx.ai Deep Dive",
                    "duration": "80 hours",
                    "topics": [
                        "Foundation models and fine-tuning",
                        "Prompt engineering best practices",
                        "Custom model development",
                        "Performance optimization"
                    ],
                    "labs": [
                        "Fine-tune Granite for logistics",
                        "Build demand forecasting model",
                        "Optimize inference costs"
                    ]
                },
                {
                    "title": "Week 5-6: Data & Governance",
                    "duration": "80 hours",
                    "topics": [
                        "watsonx.data architecture",
                        "Data pipeline development",
                        "Model governance implementation",
                        "Compliance automation"
                    ],
                    "labs": [
                        "Build real-time data pipeline",
                        "Implement bias detection",
                        "Create governance dashboards"
                    ]
                },
                {
                    "title": "Week 7-8: Automation & Integration",
                    "duration": "80 hours",
                    "topics": [
                        "Watson Orchestrate development",
                        "Multi-agent systems",
                        "Enterprise integration patterns",
                        "API development"
                    ],
                    "labs": [
                        "Build supply chain automation",
                        "Create multi-agent workflow",
                        "Integrate with SAP/Oracle"
                    ]
                },
                {
                    "title": "Week 9-10: Advanced Topics",
                    "duration": "80 hours",
                    "topics": [
                        "Production deployment strategies",
                        "Performance tuning and scaling",
                        "Security best practices",
                        "Monitoring and maintenance"
                    ],
                    "labs": [
                        "Deploy to production",
                        "Implement monitoring",
                        "Stress testing and optimization"
                    ]
                }
            ]
        },
        "Business Analyst Track": {
            "duration": "3 weeks",
            "audience": "Business Analysts, Product Managers",
            "modules": [
                {
                    "title": "Week 1: Watson for Business Analysis",
                    "duration": "40 hours",
                    "topics": [
                        "Understanding AI capabilities",
                        "Use case identification",
                        "Requirements gathering for AI",
                        "Success metrics definition"
                    ]
                },
                {
                    "title": "Week 2: Process Automation",
                    "duration": "40 hours",
                    "topics": [
                        "Process mining with Watson",
                        "Workflow design principles",
                        "Watson Orchestrate basics",
                        "ROI calculation methods"
                    ]
                },
                {
                    "title": "Week 3: Implementation Support",
                    "duration": "40 hours",
                    "topics": [
                        "Testing AI solutions",
                        "User acceptance criteria",
                        "Change management",
                        "Documentation best practices"
                    ]
                }
            ]
        },
        "Operations Track": {
            "duration": "2 weeks",
            "audience": "IT Operations, Support Teams",
            "modules": [
                {
                    "title": "Week 1: Watson Operations",
                    "duration": "40 hours",
                    "topics": [
                        "Watson infrastructure overview",
                        "Monitoring and alerting",
                        "Performance management",
                        "Troubleshooting common issues"
                    ]
                },
                {
                    "title": "Week 2: Support & Maintenance",
                    "duration": "40 hours",
                    "topics": [
                        "Model retraining procedures",
                        "Data quality management",
                        "Security and compliance",
                        "Disaster recovery"
                    ]
                }
            ]
        }
    }
    
    # Display training tracks
    col1, col2 = st.columns([1, 2])
    
    with col1:
        selected_track = st.selectbox("Select Training Track", list(training_tracks.keys()))
    
    with col2:
        track_info = training_tracks[selected_track]
        st.markdown(f"**Duration:** {track_info['duration']}")
        st.markdown(f"**Target Audience:** {track_info['audience']}")
    
    # Display modules for selected track
    st.markdown(f"### 📚 {selected_track} Modules")
    
    for module in track_info['modules']:
        with st.expander(f"**{module['title']}** ({module['duration']})"):
            st.markdown("**Topics Covered:**")
            for topic in module['topics']:
                st.markdown(f"• {topic}")
            
            if 'labs' in module:
                st.markdown("**Hands-on Labs:**")
                for lab in module['labs']:
                    st.markdown(f"🔬 {lab}")
    
    # Certification paths
    st.markdown("### 🏆 Certification Pathways")
    
    cert_data = {
        "Certification": [
            "IBM AI Developer Professional",
            "Watson Specialist - Assistant",
            "Watson Specialist - watsonx.ai",
            "Watson Specialist - Governance",
            "IBM AI Enterprise Architect",
            "Watson Solution Architect"
        ],
        "Level": ["Foundation", "Intermediate", "Intermediate", "Intermediate", "Advanced", "Advanced"],
        "Duration": ["3-6 months", "2 months", "2 months", "2 months", "6-9 months", "6-9 months"],
        "Prerequisites": ["None", "AI Developer", "AI Developer", "AI Developer", "3 Specialist Certs", "3 Specialist Certs"],
        "Relevance": ["General AI skills", "Customer service", "Model development", "Compliance", "Architecture", "Solution design"]
    }
    
    df_cert = pd.DataFrame(cert_data)
    st.dataframe(df_cert, use_container_width=True)
    
    # Training timeline
    st.markdown("### 📅 Recommended Training Timeline")
    
    timeline_data = {
        "Phase": ["Foundation", "Core Skills", "Specialization", "Advanced", "Certification"],
        "Month": [1, 2, 3, 4, 5],
        "Activities": [
            "Watson overview, basic concepts",
            "Hands-on labs, first projects",
            "Track-specific deep dives",
            "Complex implementations",
            "Exam preparation"
        ]
    }
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=timeline_data["Month"],
        y=timeline_data["Phase"],
        mode='markers+lines+text',
        marker=dict(size=20, color='blue'),
        text=timeline_data["Activities"],
        textposition="top center",
        line=dict(width=3)
    ))
    
    fig.update_layout(
        title="Training Journey Timeline",
        xaxis_title="Month",
        yaxis_title="Training Phase",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

elif selected_tab == "Governance Framework":
    st.markdown('<h2 class="sub-header">🛡️ Comprehensive AI Governance Framework</h2>', unsafe_allow_html=True)
    
    # Governance pillars
    st.markdown("### 🏛️ Four Pillars of AI Governance for UPS")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("""
        <div class="info-box">
        <h4>1️⃣ Ethical AI</h4>
        <ul>
        <li>Fairness & bias prevention</li>
        <li>Transparency & explainability</li>
        <li>Human oversight</li>
        <li>Privacy protection</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="success-box">
        <h4>2️⃣ Risk Management</h4>
        <ul>
        <li>Model risk assessment</li>
        <li>Operational risk controls</li>
        <li>Financial risk monitoring</li>
        <li>Reputation protection</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="warning-box">
        <h4>3️⃣ Compliance</h4>
        <ul>
        <li>Regulatory adherence</li>
        <li>Industry standards</li>
        <li>Data protection laws</li>
        <li>Audit readiness</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown("""
        <div class="metric-card">
        <h4>4️⃣ Performance</h4>
        <ul>
        <li>Model accuracy tracking</li>
        <li>Business impact metrics</li>
        <li>Continuous improvement</li>
        <li>Innovation balance</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Detailed governance framework
    st.markdown("### 📋 Watson Governance Implementation Framework")
    
    governance_framework = {
        "1. Model Development Governance": {
            "objectives": [
                "Ensure ethical AI development",
                "Maintain development standards",
                "Track model lineage"
            ],
            "watson_tools": [
                "watsonx.governance development tracking",
                "Watson Studio collaboration features",
                "Automated documentation generation"
            ],
            "processes": [
                "Mandatory ethics review for all models",
                "Peer review process for algorithms",
                "Automated bias testing in development",
                "Version control and change tracking"
            ],
            "metrics": [
                "Models passing ethics review: Target 100%",
                "Development cycle time: <30 days",
                "Documentation completeness: 100%"
            ]
        },
        "2. Deployment Governance": {
            "objectives": [
                "Safe and controlled deployments",
                "Risk mitigation",
                "Compliance verification"
            ],
            "watson_tools": [
                "watsonx.governance deployment gates",
                "Automated compliance checking",
                "Risk scoring algorithms"
            ],
            "processes": [
                "Multi-stage deployment approval",
                "Automated testing pipelines",
                "Rollback procedures",
                "A/B testing requirements"
            ],
            "metrics": [
                "Deployment success rate: >95%",
                "Rollback frequency: <5%",
                "Compliance violations: 0"
            ]
        },
        "3. Operational Governance": {
            "objectives": [
                "Continuous monitoring",
                "Performance optimization",
                "Incident management"
            ],
            "watson_tools": [
                "Real-time model monitoring",
                "Drift detection algorithms",
                "Automated alerting systems"
            ],
            "processes": [
                "24/7 model monitoring",
                "Weekly performance reviews",
                "Monthly governance meetings",
                "Quarterly audits"
            ],
            "metrics": [
                "Model uptime: 99.9%",
                "Drift detection time: <24 hours",
                "Incident resolution: <4 hours"
            ]
        },
        "4. Compliance & Regulatory": {
            "objectives": [
                "Meet all regulatory requirements",
                "Maintain audit trails",
                "Ensure data protection"
            ],
            "watson_tools": [
                "Compliance accelerators",
                "Automated reporting",
                "Audit trail generation"
            ],
            "regulations": {
                "Global": ["EU AI Act", "ISO 42001", "ISO 27001"],
                "Regional": ["GDPR (EU)", "CCPA (US)", "PIPL (China)"],
                "Industry": ["Transportation regulations", "Customs compliance", "Labor laws"]
            },
            "metrics": [
                "Regulatory violations: 0",
                "Audit findings: <5 minor",
                "Compliance score: 100%"
            ]
        }
    }
    
    # Display governance framework details
    for area, details in governance_framework.items():
        with st.expander(f"**{area}**"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Objectives:**")
                for obj in details['objectives']:
                    st.markdown(f"• {obj}")
                
                st.markdown("**Watson Tools & Features:**")
                for tool in details['watson_tools']:
                    st.markdown(f"• {tool}")
            
            with col2:
                if 'processes' in details:
                    st.markdown("**Key Processes:**")
                    for process in details['processes']:
                        st.markdown(f"• {process}")
                
                if 'regulations' in details:
                    st.markdown("**Regulatory Coverage:**")
                    for category, regs in details['regulations'].items():
                        st.markdown(f"**{category}:** {', '.join(regs)}")
                
                st.markdown("**Success Metrics:**")
                for metric in details['metrics']:
                    st.markdown(f"• {metric}")
    
    # Risk matrix
    st.markdown("### 🎯 AI Risk Assessment Matrix")
    
    risk_data = {
        'Risk Category': [
            'Model Bias', 
            'Data Privacy Breach', 
            'Regulatory Non-compliance',
            'Model Failure', 
            'Cyber Security',
            'Reputation Damage',
            'Operational Disruption'
        ],
        'Likelihood': [3, 2, 2, 3, 2, 2, 3],
        'Impact': [4, 5, 5, 4, 5, 4, 3],
        'Mitigation': [
            'watsonx.governance bias detection',
            'Data encryption and access controls',
            'Compliance accelerators',
            'Real-time monitoring',
            'Security frameworks',
            'Transparency measures',
            'Redundancy and failover'
        ]
    }
    
    df_risk = pd.DataFrame(risk_data)
    df_risk['Risk Score'] = df_risk['Likelihood'] * df_risk['Impact']
    
    fig = px.scatter(df_risk, x='Likelihood', y='Impact', 
                     size='Risk Score', 
                     hover_data=['Risk Category', 'Mitigation'],
                     color='Risk Score',
                     color_continuous_scale='RdYlGn_r',
                     title='AI Risk Assessment Matrix')
    
    fig.update_layout(
        xaxis=dict(title='Likelihood (1-5)', range=[0, 6]),
        yaxis=dict(title='Impact (1-5)', range=[0, 6]),
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Governance committee structure
    st.markdown("### 👥 AI Governance Committee Structure")
    
    committee_structure = {
        "Executive Steering Committee": {
            "members": ["UPS CTO", "TechM Delivery Head", "IBM Executive Sponsor"],
            "frequency": "Monthly",
            "responsibilities": ["Strategic direction", "Major decisions", "Resource allocation"]
        },
        "Technical Review Board": {
            "members": ["AI Architects", "Data Scientists", "Security Leaders"],
            "frequency": "Weekly",
            "responsibilities": ["Model reviews", "Technical standards", "Architecture decisions"]
        },
        "Ethics & Compliance Board": {
            "members": ["Legal", "Compliance Officers", "Ethics Advisors"],
            "frequency": "Bi-weekly",
            "responsibilities": ["Ethics reviews", "Compliance verification", "Policy updates"]
        },
        "Risk Management Committee": {
            "members": ["Risk Officers", "Business Leaders", "Technical Experts"],
            "frequency": "Weekly",
            "responsibilities": ["Risk assessment", "Mitigation strategies", "Incident response"]
        }
    }
    
    for committee, details in committee_structure.items():
        st.markdown(f"**{committee}**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Members:** {', '.join(details['members'])}")
        with col2:
            st.markdown(f"**Meeting Frequency:** {details['frequency']}")
        with col3:
            st.markdown(f"**Key Responsibilities:** {', '.join(details['responsibilities'])}")

elif selected_tab == "IBM Requirements":
    st.markdown('<h2 class="sub-header">📋 Requirements from IBM for Successful Implementation</h2>', unsafe_allow_html=True)
    
    # Categories of requirements
    requirements_categories = {
        "🤝 Partnership & Support Requirements": {
            "Executive Sponsorship": {
                "requirement": "Dedicated IBM executive sponsor",
                "details": [
                    "Senior VP or Director level engagement",
                    "Monthly steering committee participation",
                    "Direct escalation path for critical issues",
                    "Strategic guidance on Watson roadmap"
                ],
                "commitment_needed": "Named executive with authority to mobilize IBM resources"
            },
            "Technical Support Structure": {
                "requirement": "Premier Support Package",
                "details": [
                    "24x7 technical support coverage",
                    "Dedicated technical account manager",
                    "Priority issue resolution (4-hour SLA)",
                    "Access to Watson product teams"
                ],
                "commitment_needed": "Premium support contract covering all Watson products"
            },
            "Professional Services": {
                "requirement": "IBM Expert Labs engagement",
                "details": [
                    "6-month embedded team for initial implementation",
                    "Architecture review and optimization",
                    "Best practices knowledge transfer",
                    "Custom solution development support"
                ],
                "commitment_needed": "Minimum 5,000 hours of professional services"
            }
        },
        "💰 Commercial Requirements": {
            "Licensing Structure": {
                "requirement": "Enterprise License Agreement (ELA)",
                "details": [
                    "Unlimited usage rights for UPS globally",
                    "Flexible deployment options (cloud/on-prem)",
                    "Consumption-based pricing model",
                    "Annual true-up process"
                ],
                "commitment_needed": "$50M+ annual commitment across Watson portfolio"
            },
            "Pricing Considerations": {
                "requirement": "Volume-based discounts",
                "details": [
                    "Tier 1 pricing (highest discount level)",
                    "Multi-year commitment benefits",
                    "Bundle pricing across products",
                    "Success-based pricing components"
                ],
                "commitment_needed": "3-year minimum commitment with growth targets"
            },
            "Investment Protection": {
                "requirement": "Technology investment guarantees",
                "details": [
                    "Product roadmap commitments",
                    "Migration support for deprecated features",
                    "IP indemnification",
                    "Performance SLAs"
                ],
                "commitment_needed": "Contractual guarantees on product continuity"
            }
        },
        "🔧 Technical Requirements": {
            "Infrastructure Support": {
                "requirement": "Hybrid cloud enablement",
                "details": [
                    "Red Hat OpenShift implementation support",
                    "Multi-cloud deployment capabilities",
                    "Edge computing support for facilities",
                    "Network optimization guidance"
                ],
                "commitment_needed": "IBM Cloud credits and infrastructure consulting"
            },
            "Integration Capabilities": {
                "requirement": "Enterprise integration support",
                "details": [
                    "Pre-built connectors for UPS systems",
                    "API development assistance",
                    "Data migration tools and support",
                    "Legacy system integration patterns"
                ],
                "commitment_needed": "Custom connector development for 20+ systems"
            },
            "Security & Compliance": {
                "requirement": "Enterprise security framework",
                "details": [
                    "Security assessment and hardening",
                    "Compliance certification support",
                    "Penetration testing services",
                    "Security incident response team"
                ],
                "commitment_needed": "Quarterly security reviews and annual audits"
            }
        },
        "👥 Enablement Requirements": {
            "Training & Certification": {
                "requirement": "Comprehensive education program",
                "details": [
                    "Onsite training for 500+ TechM staff",
                    "Certification vouchers for all roles",
                    "Access to IBM learning platforms",
                    "Custom curriculum development"
                ],
                "commitment_needed": "IBM-led training bootcamps and ongoing education"
            },
            "Knowledge Transfer": {
                "requirement": "Deep technical enablement",
                "details": [
                    "Source code access where applicable",
                    "Architecture deep dives",
                    "Internal IBM documentation access",
                    "Regular tech talks with product teams"
                ],
                "commitment_needed": "NDA-level access to technical details"
            },
            "Innovation Partnership": {
                "requirement": "Co-innovation opportunities",
                "details": [
                    "Early access to beta features",
                    "Joint research projects",
                    "Patent sharing agreements",
                    "Industry solution development"
                ],
                "commitment_needed": "Strategic partnership agreement"
            }
        },
        "📊 Success Enablement": {
            "Reference Architecture": {
                "requirement": "UPS-specific blueprints",
                "details": [
                    "Logistics industry reference architectures",
                    "Implementation patterns and anti-patterns",
                    "Performance benchmarks",
                    "Scaling guidelines"
                ],
                "commitment_needed": "Customized architecture documentation"
            },
            "Success Metrics Framework": {
                "requirement": "KPI measurement tools",
                "details": [
                    "ROI calculation methodologies",
                    "Business value dashboards",
                    "Model performance tracking",
                    "Executive reporting templates"
                ],
                "commitment_needed": "Quarterly business reviews with IBM"
            },
            "Change Management": {
                "requirement": "Organizational transformation support",
                "details": [
                    "Change management methodology",
                    "Executive communication support",
                    "Success story development",
                    "Industry benchmarking data"
                ],
                "commitment_needed": "IBM transformation consulting engagement"
            }
        }
    }
    
    # Display requirements by category
    for category, requirements in requirements_categories.items():
        st.markdown(f"### {category}")
        
        for req_name, req_details in requirements.items():
            with st.expander(f"**{req_name}**"):
                st.markdown(f"**Core Requirement:** {req_details['requirement']}")
                
                st.markdown("**Detailed Requirements:**")
                for detail in req_details['details']:
                    st.markdown(f"• {detail}")
                
                st.info(f"**IBM Commitment Needed:** {req_details['commitment_needed']}")
    
    # IBM Resource Requirements Summary
    st.markdown("### 📊 IBM Resource Commitment Summary")
    
    resource_data = {
        "Resource Type": [
            "Executive Sponsors",
            "Technical Architects",
            "Data Scientists",
            "Professional Services",
            "Support Engineers",
            "Training Instructors",
            "Project Managers"
        ],
        "Initial Phase (0-6 months)": [1, 5, 3, 20, 10, 5, 3],
        "Implementation (6-12 months)": [1, 3, 2, 10, 15, 3, 2],
        "Steady State (12+ months)": [1, 2, 1, 5, 20, 2, 1],
        "Total FTE Commitment": [1, 5, 3, 20, 20, 5, 3]
    }
    
    df_resources = pd.DataFrame(resource_data)
    
    fig = go.Figure()
    
    phases = ["Initial Phase (0-6 months)", "Implementation (6-12 months)", "Steady State (12+ months)"]
    
    for phase in phases:
        fig.add_trace(go.Bar(
            name=phase,
            x=df_resources["Resource Type"],
            y=df_resources[phase]
        ))
    
    fig.update_layout(
        title="IBM Resource Commitment by Phase",
        xaxis_title="Resource Type",
        yaxis_title="Number of FTEs",
        barmode='group',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Critical Success Factors from IBM
    st.markdown("### ⚡ Critical Success Factors from IBM")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="success-box">
        <h4>✅ IBM Must Deliver</h4>
        <ul>
        <li>Product stability and reliability (99.9% SLA)</li>
        <li>Roadmap transparency and input acceptance</li>
        <li>Rapid issue resolution and escalation</li>
        <li>Continuous innovation and feature delivery</li>
        <li>Industry-specific enhancements</li>
        <li>Global support coverage</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="warning-box">
        <h4>⚠️ Risk Mitigation Requirements</h4>
        <ul>
        <li>Vendor lock-in prevention strategies</li>
        <li>Exit clause definitions</li>
        <li>Data portability guarantees</li>
        <li>Performance penalties</li>
        <li>Technology obsolescence protection</li>
        <li>Competitive pricing reviews</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

elif selected_tab == "Implementation Roadmap":
    st.markdown('<h2 class="sub-header">🗺️ Detailed Implementation Roadmap</h2>', unsafe_allow_html=True)
    
    # Phase overview
    phases = {
        "Phase 1: Foundation (Months 1-3)": {
            "objectives": [
                "Establish governance structure",
                "Set up infrastructure",
                "Complete initial training",
                "Launch pilot projects"
            ],
            "deliverables": [
                "Watson environment setup",
                "Governance committee formation",
                "Trained core team (50 people)",
                "2-3 pilot implementations"
            ],
            "milestones": {
                "Month 1": ["Infrastructure setup", "Team onboarding"],
                "Month 2": ["First pilot launch", "Training completion"],
                "Month 3": ["Pilot results", "Phase 2 planning"]
            },
            "budget": "$5M",
            "resources": "20 FTEs"
        },
        "Phase 2: Expansion (Months 4-6)": {
            "objectives": [
                "Scale successful pilots",
                "Implement core use cases",
                "Expand training program",
                "Establish CoE"
            ],
            "deliverables": [
                "5-7 production implementations",
                "Center of Excellence",
                "Trained extended team (200 people)",
                "Initial ROI demonstration"
            ],
            "milestones": {
                "Month 4": ["Production deployments", "CoE launch"],
                "Month 5": ["Integration completion", "Metrics dashboard"],
                "Month 6": ["ROI validation", "Scale planning"]
            },
            "budget": "$15M",
            "resources": "50 FTEs"
        },
        "Phase 3: Optimization (Months 7-9)": {
            "objectives": [
                "Optimize deployed solutions",
                "Implement advanced use cases",
                "Full governance rollout",
                "Performance tuning"
            ],
            "deliverables": [
                "15+ production implementations",
                "Full governance framework",
                "Performance optimization",
                "Advanced analytics"
            ],
            "milestones": {
                "Month 7": ["Advanced features", "Governance automation"],
                "Month 8": ["Performance optimization", "Cost reduction"],
                "Month 9": ["Full integration", "Readiness assessment"]
            },
            "budget": "$20M",
            "resources": "75 FTEs"
        },
        "Phase 4: Scale (Months 10-12)": {
            "objectives": [
                "Global rollout",
                "Full production scale",
                "Continuous improvement",
                "Innovation pipeline"
            ],
            "deliverables": [
                "30+ implementations",
                "Global deployment",
                "Innovation roadmap",
                "Sustained operations"
            ],
            "milestones": {
                "Month 10": ["Global rollout", "Full automation"],
                "Month 11": ["Performance validation", "Cost optimization"],
                "Month 12": ["Project closure", "Transition to BAU"]
            },
            "budget": "$25M",
            "resources": "100 FTEs"
        }
    }
    
    # Display phase selector
    selected_phase = st.selectbox("Select Phase for Detailed View", list(phases.keys()))
    
    # Display phase details
    phase_info = phases[selected_phase]
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown("### 🎯 Objectives")
        for obj in phase_info['objectives']:
            st.markdown(f"• {obj}")
        
        st.markdown("### 📦 Key Deliverables")
        for deliverable in phase_info['deliverables']:
            st.markdown(f"• {deliverable}")
    
    with col2:
        st.metric("Budget", phase_info['budget'])
        st.metric("Resources", phase_info['resources'])
    
    with col3:
        st.markdown("### 📅 Monthly Milestones")
        for month, milestones in phase_info['milestones'].items():
            st.markdown(f"**{month}:**")
            for milestone in milestones:
                st.markdown(f"• {milestone}")
    
    # Gantt chart
    st.markdown("### 📊 Implementation Timeline - Gantt Chart")
    
    gantt_data = []
    
    # Define activities with dependencies
    activities = [
        # Phase 1
        {"Task": "Infrastructure Setup", "Start": "2025-01-01", "Duration": 30, "Phase": "Foundation"},
        {"Task": "Team Formation", "Start": "2025-01-01", "Duration": 15, "Phase": "Foundation"},
        {"Task": "Initial Training", "Start": "2025-01-15", "Duration": 45, "Phase": "Foundation"},
        {"Task": "Pilot Projects", "Start": "2025-02-01", "Duration": 60, "Phase": "Foundation"},
        
        # Phase 2
        {"Task": "Production Deployment", "Start": "2025-04-01", "Duration": 90, "Phase": "Expansion"},
        {"Task": "CoE Establishment", "Start": "2025-04-01", "Duration": 30, "Phase": "Expansion"},
        {"Task": "Integration Work", "Start": "2025-04-15", "Duration": 60, "Phase": "Expansion"},
        
        # Phase 3
        {"Task": "Advanced Features", "Start": "2025-07-01", "Duration": 90, "Phase": "Optimization"},
        {"Task": "Governance Rollout", "Start": "2025-07-01", "Duration": 60, "Phase": "Optimization"},
        {"Task": "Performance Tuning", "Start": "2025-08-01", "Duration": 60, "Phase": "Optimization"},
        
        # Phase 4
        {"Task": "Global Rollout", "Start": "2025-10-01", "Duration": 90, "Phase": "Scale"},
        {"Task": "Knowledge Transfer", "Start": "2025-11-01", "Duration": 60, "Phase": "Scale"},
        {"Task": "Transition to BAU", "Start": "2025-12-01", "Duration": 30, "Phase": "Scale"}
    ]
    
    # Create Gantt chart
    fig = go.Figure()
    
    colors = {
        "Foundation": "#3182CE",
        "Expansion": "#38A169", 
        "Optimization": "#D69E2E",
        "Scale": "#E53E3E"
    }
    
    for activity in activities:
        start_date = pd.to_datetime(activity["Start"])
        end_date = start_date + pd.Timedelta(days=activity["Duration"])
        
        fig.add_trace(go.Scatter(
            x=[start_date, end_date],
            y=[activity["Task"], activity["Task"]],
            mode='lines',
            line=dict(color=colors[activity["Phase"]], width=20),
            name=activity["Phase"],
            showlegend=False,
            hovertemplate=f"<b>{activity['Task']}</b><br>Start: {start_date.strftime('%Y-%m-%d')}<br>End: {end_date.strftime('%Y-%m-%d')}<br>Duration: {activity['Duration']} days"
        ))
    
    fig.update_layout(
        title="UPS Watson Implementation Timeline",
        xaxis_title="Timeline",
        yaxis_title="Activities",
        height=600,
        xaxis=dict(type='date'),
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Risk mitigation timeline
    st.markdown("### ⚠️ Risk Mitigation Schedule")
    
    risk_timeline = {
        "Month 1-2": {
            "risks": ["Technical complexity", "Resource availability"],
            "mitigation": ["IBM architects embedded", "Dedicated hiring"]
        },
        "Month 3-4": {
            "risks": ["Pilot failure", "Stakeholder buy-in"],
            "mitigation": ["Multiple pilot options", "Executive workshops"]
        },
        "Month 5-6": {
            "risks": ["Integration challenges", "Performance issues"],
            "mitigation": ["Phased integration", "Performance labs"]
        },
        "Month 7-8": {
            "risks": ["Scaling problems", "Cost overruns"],
            "mitigation": ["Gradual scaling", "Cost monitoring"]
        },
        "Month 9-10": {
            "risks": ["Change resistance", "Knowledge gaps"],
            "mitigation": ["Change champions", "Intensive training"]
        },
        "Month 11-12": {
            "risks": ["Sustainability", "Vendor dependency"],
            "mitigation": ["CoE maturity", "Knowledge transfer"]
        }
    }
    
    for period, details in risk_timeline.items():
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**{period} - Key Risks:**")
            for risk in details['risks']:
                st.markdown(f"• 🔴 {risk}")
        with col2:
            st.markdown(f"**Mitigation Strategies:**")
            for mitigation in details['mitigation']:
                st.markdown(f"• ✅ {mitigation}")

elif selected_tab == "ROI Analysis":
    st.markdown('<h2 class="sub-header">💰 Comprehensive ROI Analysis</h2>', unsafe_allow_html=True)
    
    # Executive summary
    st.markdown("""
    <div class="success-box">
    <h3>📈 Executive Summary</h3>
    <p><b>Total Investment:</b> $65M over 12 months</p>
    <p><b>Expected Annual Savings:</b> $300M+ (based on UPS historical AI performance)</p>
    <p><b>Payback Period:</b> 2.6 months post-implementation</p>
    <p><b>5-Year NPV:</b> $1.2B (at 10% discount rate)</p>
    <p><b>IRR:</b> 362%</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Cost breakdown
    st.markdown("### 💸 Investment Breakdown")
    
    col1, col2 = st.columns(2)
    
    with col1:
        cost_data = {
            'Category': ['Watson Licenses', 'Professional Services', 'Infrastructure', 
                        'Training', 'Internal Resources', 'Contingency'],
            'Amount ($M)': [25, 15, 10, 5, 8, 2]
        }
        
        fig = px.pie(cost_data, values='Amount ($M)', names='Category',
                     title='Total Investment Distribution - $65M')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Quarterly spending
        quarterly_data = {
            'Quarter': ['Q1', 'Q2', 'Q3', 'Q4'],
            'Investment ($M)': [20, 20, 15, 10],
            'Cumulative ($M)': [20, 40, 55, 65]
        }
        
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Quarterly', x=quarterly_data['Quarter'], 
                            y=quarterly_data['Investment ($M)']))
        fig.add_trace(go.Scatter(name='Cumulative', x=quarterly_data['Quarter'], 
                                y=quarterly_data['Cumulative ($M)'], 
                                mode='lines+markers', yaxis='y2'))
        
        fig.update_layout(
            title='Investment Timeline',
            yaxis=dict(title='Quarterly Investment ($M)'),
            yaxis2=dict(title='Cumulative Investment ($M)', overlaying='y', side='right'),
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Benefit categories
    st.markdown("### 💰 Benefit Analysis by Category")
    
    benefit_categories = {
        "Operational Efficiency": {
            "Route Optimization": 100,
            "Automated Sorting": 40,
            "Predictive Maintenance": 80,
            "Workforce Optimization": 30
        },
        "Customer Experience": {
            "Support Automation": 100,
            "Faster Delivery": 50,
            "Proactive Communication": 20,
            "Self-Service": 30
        },
        "Risk Reduction": {
            "Compliance Automation": 50,
            "Fraud Prevention": 30,
            "Accident Reduction": 50,
            "Disruption Mitigation": 70
        },
        "Innovation Revenue": {
            "New Services": 100,
            "Premium Offerings": 50,
            "Data Monetization": 30,
            "Partner Ecosystem": 20
        }
    }
    
    # Create benefit visualization
    benefit_data = []
    for category, items in benefit_categories.items():
        for item, value in items.items():
            benefit_data.append({
                'Category': category,
                'Benefit': item,
                'Annual Value ($M)': value
            })
    
    df_benefits = pd.DataFrame(benefit_data)
    
    fig = px.sunburst(df_benefits, path=['Category', 'Benefit'], 
                      values='Annual Value ($M)',
                      title='Annual Benefit Distribution - $850M Total')
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)
    
    # ROI timeline
    st.markdown("### 📊 ROI Timeline Analysis")
    
    months = list(range(1, 61))  # 5 years
    investment = [65 if i <= 12 else 5 for i in months]  # Initial + maintenance
    benefits = [0 if i <= 3 else 300/12 if i <= 12 else 850/12 for i in months]  # Ramp up
    cumulative_roi = []
    
    total_investment = 0
    total_benefit = 0
    
    for i in range(len(months)):
        total_investment += investment[i]
        total_benefit += benefits[i]
        cumulative_roi.append(total_benefit - total_investment)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=months,
        y=cumulative_roi,
        mode='lines',
        name='Cumulative ROI',
        fill='tozeroy',
        line=dict(width=3)
    ))
    
    # Add break-even line
    fig.add_hline(y=0, line_dash="dash", line_color="red", 
                  annotation_text="Break-even")
    
    fig.update_layout(
        title='5-Year ROI Projection',
        xaxis_title='Months',
        yaxis_title='Cumulative ROI ($M)',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Sensitivity analysis
    st.markdown("### 🎯 Sensitivity Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        benefit_reduction = st.slider("Benefit Reduction %", 0, 50, 0, 5)
        cost_increase = st.slider("Cost Increase %", 0, 50, 0, 5)
    
    with col2:
        adjusted_benefits = 850 * (1 - benefit_reduction/100)
        adjusted_costs = 65 * (1 + cost_increase/100)
        adjusted_roi = (adjusted_benefits - adjusted_costs) / adjusted_costs * 100
        
        st.metric("Adjusted Annual Benefits", f"${adjusted_benefits:.0f}M")
        st.metric("Adjusted Investment", f"${adjusted_costs:.0f}M")
        st.metric("Adjusted ROI", f"{adjusted_roi:.0f}%", 
                 delta=f"{adjusted_roi - 1207:.0f}% vs base case")
    
    # Comparison with industry benchmarks
    st.markdown("### 📊 Industry Benchmark Comparison")
    
    benchmark_data = {
        'Company': ['UPS (Current)', 'UPS (with Watson)', 'FedEx', 'DHL', 'Industry Avg'],
        'AI Investment % of Revenue': [0.5, 2.0, 1.5, 1.2, 1.0],
        'Operational Efficiency Gain': [10, 40, 25, 20, 15],
        'Customer Satisfaction Score': [82, 95, 85, 80, 78]
    }
    
    df_benchmark = pd.DataFrame(benchmark_data)
    
    fig = go.Figure()
    
    categories = ['AI Investment % of Revenue', 'Operational Efficiency Gain', 'Customer Satisfaction Score']
    
    for i, company in enumerate(df_benchmark['Company']):
        values = [df_benchmark.iloc[i][cat] for cat in categories]
        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=categories,
            fill='toself',
            name=company
        ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100]
            )),
        showlegend=True,
        title="Competitive Positioning Analysis"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Key success metrics
    st.markdown("### 🎯 Key Success Metrics & Targets")
    
    metrics_data = {
        "Metric": [
            "Package Sorting Accuracy",
            "Delivery Time Reduction",
            "Customer Query Resolution",
            "Route Optimization Efficiency",
            "Predictive Maintenance Accuracy",
            "Carbon Footprint Reduction"
        ],
        "Current": [95, 0, 60, 85, 70, 10],
        "Year 1 Target": [99, 15, 80, 92, 85, 20],
        "Year 3 Target": [99.9, 25, 95, 97, 95, 35]
    }
    
    df_metrics = pd.DataFrame(metrics_data)
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(name='Current', x=df_metrics['Metric'], y=df_metrics['Current']))
    fig.add_trace(go.Bar(name='Year 1 Target', x=df_metrics['Metric'], y=df_metrics['Year 1 Target']))
    fig.add_trace(go.Bar(name='Year 3 Target', x=df_metrics['Metric'], y=df_metrics['Year 3 Target']))
    
    fig.update_layout(
        title='Performance Improvement Targets (%)',
        xaxis_tickangle=-45,
        barmode='group',
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>UPS-IBM Watson Strategic Implementation Platform | TechM Leadership Dashboard</p>
    <p>Last Updated: January 2025 | Version 1.0</p>
</div>
""", unsafe_allow_html=True)
