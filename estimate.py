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
        'PS-EPIC-03': {
            'name': 'Warehouse & Inventory Management',
            'system': 'Polar Scan',
            'complexity': 'High',
            'capabilities': {
                'PS-CAP-3.1': {
                    'name': 'Pharmacy inventory management',
                    'stories': ['Real-time pharmaceutical visibility', 'Track controlled substances', 'Compliance tracking'],
                    'points': 8
                },
                'PS-CAP-3.2': {
                    'name': 'Location and bin management',
                    'stories': ['Perform bin putaway', 'Move inventory between locations', 'Location optimization'],
                    'points': 5
                },
                'PS-CAP-3.3': {
                    'name': 'Cycle counting and adjustments',
                    'stories': ['Perform cycle counting', 'Adjust inventory with reasons', 'Reconciliation workflows'],
                    'points': 5
                },
                'PS-CAP-3.4': {
                    'name': 'Lot/batch/serial tracking',
                    'stories': ['Track lot numbers', 'Track expiry dates', 'Serial number management'],
                    'points': 5
                },
                'PS-CAP-3.5': {
                    'name': 'Expiry and FEFO management',
                    'stories': ['Enforce FEFO rules', 'Quarantine expired items', 'Expiry alerts'],
                    'points': 5
                }
            }
        },
        'PS-EPIC-04': {
            'name': 'Temperature Zone Operations',
            'system': 'Polar Scan',
            'complexity': 'Very High',
            'capabilities': {
                'PS-CAP-4.1': {
                    'name': 'Temperature zone identification',
                    'stories': ['Identify temperature requirements at scan', 'Temperature validation', 'Zone routing logic'],
                    'points': 8
                },
                'PS-CAP-4.2': {
                    'name': 'Ambient zone operations',
                    'stories': ['Route items to ambient zones', 'Ambient zone management', 'Zone capacity tracking'],
                    'points': 3
                },
                'PS-CAP-4.3': {
                    'name': 'Chilled zone management',
                    'stories': ['Route to chilled zones (2-8°C)', 'Chilled chamber monitoring', 'Temperature compliance'],
                    'points': 8
                },
                'PS-CAP-4.4': {
                    'name': 'Frozen zone management',
                    'stories': ['Route to frozen zones (-20°C)', 'Frozen storage management', 'Deep freeze monitoring'],
                    'points': 8
                },
                'PS-CAP-4.5': {
                    'name': 'Temperature validation',
                    'stories': ['Validate at checkpoints', 'Override with authorization', 'Compliance reports'],
                    'points': 5
                }
            }
        },
        'PS-EPIC-05': {
            'name': 'Staging & Bus Stop Management',
            'system': 'Polar Scan',
            'complexity': 'Medium',
            'capabilities': {
                'PS-CAP-5.1': {
                    'name': 'Staging area operations',
                    'stories': ['Move pallets to staging', 'Staging area visibility', 'Optimize utilization'],
                    'points': 3
                },
                'PS-CAP-5.2': {
                    'name': 'Bus stop allocation',
                    'stories': ['Assign bus stop locations', 'Scan pallets at bus stops', 'Bus stop management'],
                    'points': 3
                },
                'PS-CAP-5.3': {
                    'name': 'Vehicle presence detection',
                    'stories': ['Detect vehicle arrival', 'Alert when vehicles present', 'Vehicle tracking'],
                    'points': 5
                },
                'PS-CAP-5.4': {
                    'name': 'Staging to loading workflows',
                    'stories': ['Move staged pallets to vehicles', 'Loading sequence optimization', 'Clear staging areas'],
                    'points': 3
                },
                'PS-CAP-5.5': {
                    'name': 'Priority staging management',
                    'stories': ['Prioritize urgent items', 'Express lane management', 'Priority alerts'],
                    'points': 3
                }
            }
        },
        'PS-EPIC-06': {
            'name': 'Cross-docking Operations',
            'system': 'Polar Scan',
            'complexity': 'Medium',
            'capabilities': {
                'PS-CAP-6.1': {
                    'name': 'Cross-dock identification',
                    'stories': ['Identify cross-dock items', 'Cross-dock routing rules', 'Bypass storage logic'],
                    'points': 3
                },
                'PS-CAP-6.2': {
                    'name': 'Direct to outbound routing',
                    'stories': ['Route directly to outbound', 'Scan confirmations', 'Skip putaway'],
                    'points': 3
                },
                'PS-CAP-6.3': {
                    'name': 'Cross-dock performance',
                    'stories': ['Track dwell time', 'Performance metrics', 'Optimization reports'],
                    'points': 3
                },
                'PS-CAP-6.4': {
                    'name': 'Consolidation operations',
                    'stories': ['Consolidate shipments', 'Merge orders', 'Consolidation rules'],
                    'points': 5
                }
            }
        },
        'PS-EPIC-07': {
            'name': 'Outbound & Final Mile Loading',
            'system': 'Polar Scan',
            'complexity': 'High',
            'capabilities': {
                'PS-CAP-7.1': {
                    'name': 'Pick list generation',
                    'stories': ['Receive pick lists on scanner', 'Optimized pick paths', 'Batch picking'],
                    'points': 5
                },
                'PS-CAP-7.2': {
                    'name': 'Pack and ship operations',
                    'stories': ['Scan items during picking', 'Scan into packages', 'Print shipping labels'],
                    'points': 5
                },
                'PS-CAP-7.3': {
                    'name': 'Final mile vehicle loading',
                    'stories': ['Scan by delivery route', 'Load ambient chamber', 'Load chilled chamber'],
                    'points': 8
                },
                'PS-CAP-7.4': {
                    'name': 'Route-based loading',
                    'stories': ['Scan vehicle chambers', 'Route optimization', 'Loading sequence'],
                    'points': 5
                },
                'PS-CAP-7.5': {
                    'name': 'Load verification',
                    'stories': ['Validate completeness', 'Confirm departure', 'Send departure events'],
                    'points': 5
                }
            }
        },
        'PS-EPIC-08': {
            'name': 'Exception & Misdelivery Management',
            'system': 'Polar Scan',
            'complexity': 'High',
            'capabilities': {
                'PS-CAP-8.1': {
                    'name': 'Misdelivery detection',
                    'stories': ['Identify misdelivered items', 'Generate re-routing', 'Misdelivery alerts'],
                    'points': 5
                },
                'PS-CAP-8.2': {
                    'name': 'Tote bin exception handling',
                    'stories': ['Handle tote exceptions', 'Tote tracking', 'Exception workflows'],
                    'points': 5
                },
                'PS-CAP-8.3': {
                    'name': 'Damage reporting',
                    'stories': ['Report damage with photos', 'Damage workflows', 'Claims processing'],
                    'points': 5
                },
                'PS-CAP-8.4': {
                    'name': 'Temperature excursion handling',
                    'stories': ['Temperature exceptions', 'Excursion workflows', 'Quality alerts'],
                    'points': 8
                },
                'PS-CAP-8.5': {
                    'name': 'Quality exception workflows',
                    'stories': ['Root cause analysis', 'Quarantine items', 'Exception analytics'],
                    'points': 5
                }
            }
        },
        'PS-EPIC-09': {
            'name': 'System Integration',
            'system': 'Polar Scan',
            'complexity': 'Very High',
            'capabilities': {
                'PS-CAP-9.1': {
                    'name': 'Track system integration',
                    'stories': ['Post scan events real-time', 'Sync inventory with Track', 'Event streaming'],
                    'points': 13
                },
                'PS-CAP-9.2': {
                    'name': 'Temperature platform integration',
                    'stories': ['Receive temperature data', 'Temperature sync', 'IoT integration'],
                    'points': 13
                },
                'PS-CAP-9.3': {
                    'name': 'WMS synchronization',
                    'stories': ['Integrate with WMS', 'Location sync', 'Inventory sync'],
                    'points': 8
                },
                'PS-CAP-9.4': {
                    'name': 'ERP integration',
                    'stories': ['Post to Dynamics 365', 'Financial integration', 'Master data sync'],
                    'points': 8
                },
                'PS-CAP-9.5': {
                    'name': 'Event streaming',
                    'stories': ['Send notifications', 'Maintain consistency', 'Event architecture'],
                    'points': 8
                }
            }
        },
        'PS-EPIC-10': {
            'name': 'Mobile Scanner Application',
            'system': 'Polar Scan',
            'complexity': 'Very High',
            'capabilities': {
                'PS-CAP-10.1': {
                    'name': 'Zebra device optimization',
                    'stories': ['Android app on Zebra', 'Device configuration', 'Performance optimization'],
                    'points': 8
                },
                'PS-CAP-10.2': {
                    'name': 'Offline scanning',
                    'stories': ['Offline capability', 'Data sync', 'Queue management'],
                    'points': 8
                },
                'PS-CAP-10.3': {
                    'name': 'User interface',
                    'stories': ['Barcode scanning UI', 'Large buttons for gloves', 'Multi-language support'],
                    'points': 5
                },
                'PS-CAP-10.4': {
                    'name': 'Voice-directed operations',
                    'stories': ['Voice commands', 'Voice feedback', 'Hands-free operation'],
                    'points': 8
                },
                'PS-CAP-10.5': {
                    'name': 'Performance optimization',
                    'stories': ['Battery optimization', 'Quick access functions', 'Remote configuration'],
                    'points': 5
                }
            }
        },
        
        # POLAR TRACK EPICS
        'PT-EPIC-01': {
            'name': 'Customer Onboarding & Contracts',
            'system': 'Polar Track',
            'complexity': 'Medium',
            'capabilities': {
                'PT-CAP-1.1': {
                    'name': 'Customer registration portal',
                    'stories': ['Self-register online', 'Upload compliance docs', 'Digital signatures'],
                    'points': 3
                },
                'PT-CAP-1.2': {
                    'name': 'Contract management',
                    'stories': ['Create customer contracts', 'Contract templates', 'Renewal workflows'],
                    'points': 3
                },
                'PT-CAP-1.3': {
                    'name': 'Service level configuration',
                    'stories': ['Configure service levels', 'Temperature requirements', 'SLA management'],
                    'points': 3
                },
                'PT-CAP-1.4': {
                    'name': 'Pricing management',
                    'stories': ['Pricing agreements', 'Credit limits', 'Billing setup'],
                    'points': 3
                },
                'PT-CAP-1.5': {
                    'name': 'Compliance documentation',
                    'stories': ['Verify credentials', 'Compliance tracking', 'Document management'],
                    'points': 3
                }
            }
        },
        'PT-EPIC-02': {
            'name': 'Master Data Management',
            'system': 'Polar Track',
            'complexity': 'High',
            'capabilities': {
                'PT-CAP-2.1': {
                    'name': 'Product master',
                    'stories': ['Maintain product master', 'Product hierarchy', 'Product attributes'],
                    'points': 5
                },
                'PT-CAP-2.2': {
                    'name': 'Location master',
                    'stories': ['Location hierarchy', 'Facility management', 'Geographic data'],
                    'points': 5
                },
                'PT-CAP-2.3': {
                    'name': 'Carrier and services',
                    'stories': ['Carrier information', 'Service types', 'Carrier contracts'],
                    'points': 3
                },
                'PT-CAP-2.4': {
                    'name': 'Route management',
                    'stories': ['Route templates', 'Lane management', 'Route optimization'],
                    'points': 5
                },
                'PT-CAP-2.5': {
                    'name': 'Data governance',
                    'stories': ['Data quality', 'Duplicate detection', 'Audit trails'],
                    'points': 5
                }
            }
        },
        'PT-EPIC-03': {
            'name': 'Order Management & Processing',
            'system': 'Polar Track',
            'complexity': 'High',
            'capabilities': {
                'PT-CAP-3.1': {
                    'name': 'Order creation',
                    'stories': ['Create orders online', 'Bulk upload Excel', 'Order templates'],
                    'points': 5
                },
                'PT-CAP-3.2': {
                    'name': 'Order validation',
                    'stories': ['Validate order details', 'Inventory allocation', 'Credit checks'],
                    'points': 5
                },
                'PT-CAP-3.3': {
                    'name': 'Order fulfillment',
                    'stories': ['Fulfillment optimization', 'Route assignment', 'Order consolidation'],
                    'points': 8
                },
                'PT-CAP-3.4': {
                    'name': 'Order tracking',
                    'stories': ['Track order status', 'Order modifications', 'Status notifications'],
                    'points': 5
                },
                'PT-CAP-3.5': {
                    'name': 'EDI/API integration',
                    'stories': ['Receive EDI orders', 'API integration', 'Order confirmations'],
                    'points': 8
                }
            }
        },
        'PT-EPIC-04': {
            'name': 'Middle Mile Delivery Management',
            'system': 'Polar Track',
            'complexity': 'High',
            'capabilities': {
                'PT-CAP-4.1': {
                    'name': 'Hub-to-hub planning',
                    'stories': ['Plan hub routes', 'Capacity planning', 'Load optimization'],
                    'points': 5
                },
                'PT-CAP-4.2': {
                    'name': 'Hub-to-depot optimization',
                    'stories': ['Optimize depot routes', 'Multi-stop planning', 'Time windows'],
                    'points': 5
                },
                'PT-CAP-4.3': {
                    'name': 'Milk run operations',
                    'stories': ['Schedule milk runs', 'Route optimization', 'Stop sequencing'],
                    'points': 5
                },
                'PT-CAP-4.4': {
                    'name': 'Consolidation planning',
                    'stories': ['Calculate consolidations', 'LTL optimization', 'Load building'],
                    'points': 5
                },
                'PT-CAP-4.5': {
                    'name': 'Middle mile tracking',
                    'stories': ['Track vehicles', 'Monitor SLAs', 'Event tracking'],
                    'points': 5
                }
            }
        },
        'PT-EPIC-05': {
            'name': 'Hub & Depot Network Operations',
            'system': 'Polar Track',
            'complexity': 'High',
            'capabilities': {
                'PT-CAP-5.1': {
                    'name': 'Network capacity planning',
                    'stories': ['Model capacity', 'Predict needs', 'Capacity alerts'],
                    'points': 8
                },
                'PT-CAP-5.2': {
                    'name': 'Hub operations',
                    'stories': ['Manage hub ops', 'Hub dashboards', 'Performance metrics'],
                    'points': 5
                },
                'PT-CAP-5.3': {
                    'name': 'Depot optimization',
                    'stories': ['Optimize workflows', 'Depot management', 'Resource planning'],
                    'points': 5
                },
                'PT-CAP-5.4': {
                    'name': 'Inter-facility transfers',
                    'stories': ['Schedule transfers', 'Transfer tracking', 'Balance inventory'],
                    'points': 5
                },
                'PT-CAP-5.5': {
                    'name': 'Network balancing',
                    'stories': ['Balance loads', 'Identify bottlenecks', 'Utilization reports'],
                    'points': 5
                }
            }
        },
        'PT-EPIC-06': {
            'name': 'Final Mile Delivery Operations',
            'system': 'Polar Track',
            'complexity': 'Very High',
            'capabilities': {
                'PT-CAP-6.1': {
                    'name': 'Route optimization',
                    'stories': ['Optimize delivery routes', 'Dynamic routing', 'Route planning'],
                    'points': 8
                },
                'PT-CAP-6.2': {
                    'name': 'Time window management',
                    'stories': ['Select delivery windows', 'Window optimization', 'Customer preferences'],
                    'points': 5
                },
                'PT-CAP-6.3': {
                    'name': 'Proof of delivery',
                    'stories': ['Capture POD', 'Electronic signatures', 'Photo capture'],
                    'points': 5
                },
                'PT-CAP-6.4': {
                    'name': 'Failed delivery management',
                    'stories': ['Handle failures', 'Reschedule deliveries', 'Return management'],
                    'points': 5
                },
                'PT-CAP-6.5': {
                    'name': 'Customer preferences',
                    'stories': ['Delivery instructions', 'Notification preferences', 'Special requests'],
                    'points': 3
                }
            }
        },
        'PT-EPIC-07': {
            'name': 'Fleet & Driver Management',
            'system': 'Polar Track',
            'complexity': 'High',
            'capabilities': {
                'PT-CAP-7.1': {
                    'name': 'Vehicle tracking',
                    'stories': ['Track locations', 'Vehicle assignment', 'GPS monitoring'],
                    'points': 5
                },
                'PT-CAP-7.2': {
                    'name': 'Driver management',
                    'stories': ['Driver hours', 'Compliance monitoring', 'Driver scheduling'],
                    'points': 5
                },
                'PT-CAP-7.3': {
                    'name': 'Maintenance management',
                    'stories': ['Maintenance schedules', 'Service tracking', 'Preventive maintenance'],
                    'points': 3
                },
                'PT-CAP-7.4': {
                    'name': 'Performance tracking',
                    'stories': ['Driver scores', 'Fuel consumption', 'Safety metrics'],
                    'points': 5
                },
                'PT-CAP-7.5': {
                    'name': 'Fleet optimization',
                    'stories': ['Utilization metrics', 'Cost analysis', 'Fleet planning'],
                    'points': 5
                }
            }
        },
        'PT-EPIC-08': {
            'name': 'Real-time Tracking & Visibility',
            'system': 'Polar Track',
            'complexity': 'Very High',
            'capabilities': {
                'PT-CAP-8.1': {
                    'name': 'GPS/telematics integration',
                    'stories': ['GPS tracking', 'Telematics integration', 'Real-time location'],
                    'points': 8
                },
                'PT-CAP-8.2': {
                    'name': 'Milestone events',
                    'stories': ['Capture milestones', 'Event tracking', 'Status updates'],
                    'points': 5
                },
                'PT-CAP-8.3': {
                    'name': 'Customer tracking portal',
                    'stories': ['Customer visibility', 'Tracking portal', 'Mobile tracking'],
                    'points': 5
                },
                'PT-CAP-8.4': {
                    'name': 'Scan event integration',
                    'stories': ['Correlate scan/GPS', 'Event correlation', 'Data integration'],
                    'points': 8
                },
                'PT-CAP-8.5': {
                    'name': 'ETA calculations',
                    'stories': ['Calculate ETAs', 'Update estimates', 'Predictive analytics'],
                    'points': 8
                }
            }
        },
        'PT-EPIC-09': {
            'name': 'Centralized IoT & Temperature Platform',
            'system': 'Polar Track',
            'complexity': 'Very High',
            'capabilities': {
                'PT-CAP-9.1': {
                    'name': 'IoT device provisioning',
                    'stories': ['Provision devices', 'Device management', 'Configuration'],
                    'points': 8
                },
                'PT-CAP-9.2': {
                    'name': 'Temperature monitoring',
                    'stories': ['Real-time streaming', 'Threshold alerts', 'Temperature logging'],
                    'points': 13
                },
                'PT-CAP-9.3': {
                    'name': 'Environmental tracking',
                    'stories': ['Multi-parameter tracking', 'Humidity monitoring', 'Shock detection'],
                    'points': 8
                },
                'PT-CAP-9.4': {
                    'name': 'Predictive analytics',
                    'stories': ['Excursion predictions', 'MKT calculations', 'Stability budgets'],
                    'points': 13
                },
                'PT-CAP-9.5': {
                    'name': 'Compliance reporting',
                    'stories': ['Compliance certificates', 'Audit trails', 'Temperature reports'],
                    'points': 5
                }
            }
        },
        'PT-EPIC-10': {
            'name': 'Inventory & Network Visibility',
            'system': 'Polar Track',
            'complexity': 'High',
            'capabilities': {
                'PT-CAP-10.1': {
                    'name': 'Real-time inventory',
                    'stories': ['Real-time visibility', 'Stock levels', 'Inventory tracking'],
                    'points': 5
                },
                'PT-CAP-10.2': {
                    'name': 'Network visibility',
                    'stories': ['Network-wide stock', 'Cross-depot visibility', 'Global inventory'],
                    'points': 5
                },
                'PT-CAP-10.3': {
                    'name': 'Inventory allocation',
                    'stories': ['Allocation rules', 'Reservations', 'ATP visibility'],
                    'points': 5
                },
                'PT-CAP-10.4': {
                    'name': 'Stock in transit',
                    'stories': ['Transit tracking', 'In-transit inventory', 'Pipeline stock'],
                    'points': 5
                },
                'PT-CAP-10.5': {
                    'name': 'Inventory sync',
                    'stories': ['Synchronization', 'Reconciliation', 'Inventory accuracy'],
                    'points': 5
                }
            }
        },
        'PT-EPIC-11': {
            'name': 'Exception & Incident Management',
            'system': 'Polar Track',
            'complexity': 'High',
            'capabilities': {
                'PT-CAP-11.1': {
                    'name': 'Misload detection',
                    'stories': ['Detect misloads', 'Misload alerts', 'Recovery workflows'],
                    'points': 5
                },
                'PT-CAP-11.2': {
                    'name': 'Delivery exceptions',
                    'stories': ['Exception handling', 'Exception workflows', 'Customer notifications'],
                    'points': 5
                },
                'PT-CAP-11.3': {
                    'name': 'Claims management',
                    'stories': ['Damage documentation', 'Claims processing', 'Insurance integration'],
                    'points': 5
                },
                'PT-CAP-11.4': {
                    'name': 'Temperature excursions',
                    'stories': ['Excursion management', 'Quality workflows', 'Investigation'],
                    'points': 8
                },
                'PT-CAP-11.5': {
                    'name': 'Root cause analysis',
                    'stories': ['Incident analysis', 'Corrective actions', 'Trend analytics'],
                    'points': 5
                }
            }
        },
        'PT-EPIC-12': {
            'name': 'Analytics & Reporting Platform',
            'system': 'Polar Track',
            'complexity': 'High',
            'capabilities': {
                'PT-CAP-12.1': {
                    'name': 'Operational dashboards',
                    'stories': ['Real-time dashboards', 'KPI monitoring', 'Performance tracking'],
                    'points': 5
                },
                'PT-CAP-12.2': {
                    'name': 'KPI scorecards',
                    'stories': ['Executive scorecards', 'SLA monitoring', 'Benchmarking'],
                    'points': 5
                },
                'PT-CAP-12.3': {
                    'name': 'Custom reporting',
                    'stories': ['Report builder', 'Scheduled reports', 'Ad-hoc queries'],
                    'points': 5
                },
                'PT-CAP-12.4': {
                    'name': 'Compliance reporting',
                    'stories': ['Regulatory reports', 'Audit reports', 'Compliance tracking'],
                    'points': 5
                },
                'PT-CAP-12.5': {
                    'name': 'Executive analytics',
                    'stories': ['Predictive analytics', 'Trend analysis', 'Business intelligence'],
                    'points': 8
                }
            }
        },
        
        # PATIENT MANAGEMENT EPICS
        'PM-EPIC-01': {
            'name': 'Patient Registration & NHS Integration',
            'system': 'Patient Management',
            'complexity': 'High',
            'capabilities': {
                'PM-CAP-1.1': {
                    'name': 'Patient self-registration',
                    'stories': ['Self-register online', 'Personal details capture', 'Account creation'],
                    'points': 3
                },
                'PM-CAP-1.2': {
                    'name': 'NHS validation',
                    'stories': ['Validate NHS numbers', 'NHS lookup', 'Demographics retrieval'],
                    'points': 5
                },
                'PM-CAP-1.3': {
                    'name': 'Summary Care Record',
                    'stories': ['Access care records', 'Medical history', 'Allergy information'],
                    'points': 8
                },
                'PM-CAP-1.4': {
                    'name': 'Identity verification',
                    'stories': ['Verify identity', 'Duplicate checking', 'Patient matching'],
                    'points': 5
                },
                'PM-CAP-1.5': {
                    'name': 'Consent management',
                    'stories': ['Data sharing consent', 'Family access', 'Consent tracking'],
                    'points': 5
                }
            }
        },
        'PM-EPIC-02': {
            'name': 'Trust & Payer Management',
            'system': 'Patient Management',
            'complexity': 'Medium',
            'capabilities': {
                'PM-CAP-2.1': {
                    'name': 'Trust registration',
                    'stories': ['Register trusts', 'Trust management', 'Trust contracts'],
                    'points': 3
                },
                'PM-CAP-2.2': {
                    'name': 'Coverage validation',
                    'stories': ['Validate coverage', 'Patient eligibility', 'Coverage rules'],
                    'points': 3
                },
                'PM-CAP-2.3': {
                    'name': 'Funding workflows',
                    'stories': ['Funding authorization', 'Approval workflows', 'Budget tracking'],
                    'points': 5
                },
                'PM-CAP-2.4': {
                    'name': 'Trust billing',
                    'stories': ['Trust invoicing', 'Billing workflows', 'Payment tracking'],
                    'points': 3
                },
                'PM-CAP-2.5': {
                    'name': 'Budget management',
                    'stories': ['Budget limits', 'Utilization tracking', 'Cost control'],
                    'points': 3
                }
            }
        },
        'PM-EPIC-03': {
            'name': 'Prescription Receipt & Processing',
            'system': 'Patient Management',
            'complexity': 'High',
            'capabilities': {
                'PM-CAP-3.1': {
                    'name': 'Electronic prescriptions',
                    'stories': ['Receive e-prescriptions', 'Hospital integration', 'Prescription queue'],
                    'points': 5
                },
                'PM-CAP-3.2': {
                    'name': 'Prescription validation',
                    'stories': ['Validate prescriptions', 'Verification workflows', 'Completeness checks'],
                    'points': 5
                },
                'PM-CAP-3.3': {
                    'name': 'Clinical review',
                    'stories': ['Clinical checking', 'Pharmacist review', 'Intervention tracking'],
                    'points': 5
                },
                'PM-CAP-3.4': {
                    'name': 'Drug interactions',
                    'stories': ['Interaction checking', 'Allergy alerts', 'Contraindications'],
                    'points': 8
                },
                'PM-CAP-3.5': {
                    'name': 'Status tracking',
                    'stories': ['Prescription status', 'Progress tracking', 'Status notifications'],
                    'points': 3
                }
            }
        },
        'PM-EPIC-04': {
            'name': 'Treatment Planning & Protocols',
            'system': 'Patient Management',
            'complexity': 'Medium',
            'capabilities': {
                'PM-CAP-4.1': {
                    'name': 'Protocol definition',
                    'stories': ['Create protocols', 'Protocol templates', 'Clinical guidelines'],
                    'points': 5
                },
                'PM-CAP-4.2': {
                    'name': 'Care planning',
                    'stories': ['Develop care plans', 'Treatment schedules', 'Care pathways'],
                    'points': 3
                },
                'PM-CAP-4.3': {
                    'name': 'Dosage management',
                    'stories': ['Dosage calculations', 'Schedule management', 'Dose adjustments'],
                    'points': 3
                },
                'PM-CAP-4.4': {
                    'name': 'Timeline tracking',
                    'stories': ['Treatment timelines', 'Milestone tracking', 'Progress monitoring'],
                    'points': 3
                },
                'PM-CAP-4.5': {
                    'name': 'Compliance monitoring',
                    'stories': ['Protocol compliance', 'Adherence tracking', 'Deviation alerts'],
                    'points': 3
                }
            }
        },
        'PM-EPIC-05': {
            'name': 'Pharmacy Network & Operations',
            'system': 'Patient Management',
            'complexity': 'Medium',
            'capabilities': {
                'PM-CAP-5.1': {
                    'name': 'Pharmacy assignment',
                    'stories': ['Assign pharmacies', 'Patient allocation', 'Workload balancing'],
                    'points': 3
                },
                'PM-CAP-5.2': {
                    'name': 'Pharmacy inventory',
                    'stories': ['Inventory management', 'Stock tracking', 'Reorder management'],
                    'points': 3
                },
                'PM-CAP-5.3': {
                    'name': 'Dispensing workflows',
                    'stories': ['Dispensing process', 'Label printing', 'Verification checks'],
                    'points': 3
                },
                'PM-CAP-5.4': {
                    'name': 'Controlled substances',
                    'stories': ['CD handling', 'Register management', 'Compliance tracking'],
                    'points': 5
                },
                'PM-CAP-5.5': {
                    'name': 'Performance tracking',
                    'stories': ['Pharmacy metrics', 'Performance KPIs', 'Quality monitoring'],
                    'points': 3
                }
            }
        },
        'PM-EPIC-06': {
            'name': 'Scheduling & Care Coordination',
            'system': 'Patient Management',
            'complexity': 'Medium',
            'capabilities': {
                'PM-CAP-6.1': {
                    'name': 'Appointment scheduling',
                    'stories': ['Schedule appointments', 'Calendar management', 'Booking system'],
                    'points': 3
                },
                'PM-CAP-6.2': {
                    'name': 'Care coordination',
                    'stories': ['Team coordination', 'Task assignment', 'Communication'],
                    'points': 3
                },
                'PM-CAP-6.3': {
                    'name': 'Resource optimization',
                    'stories': ['Resource scheduling', 'Capacity management', 'Optimization'],
                    'points': 5
                },
                'PM-CAP-6.4': {
                    'name': 'MDT management',
                    'stories': ['Multi-disciplinary teams', 'Team meetings', 'Care conferences'],
                    'points': 3
                },
                'PM-CAP-6.5': {
                    'name': 'Conflict resolution',
                    'stories': ['Conflict detection', 'Schedule adjustments', 'Priority management'],
                    'points': 3
                }
            }
        },
        'PM-EPIC-07': {
            'name': 'Phlebotomy Services Management',
            'system': 'Patient Management',
            'complexity': 'Medium',
            'capabilities': {
                'PM-CAP-7.1': {
                    'name': 'Phlebotomy scheduling',
                    'stories': ['Schedule blood draws', 'Route planning', 'Time slots'],
                    'points': 3
                },
                'PM-CAP-7.2': {
                    'name': 'Mobile operations',
                    'stories': ['Mobile phlebotomy', 'Daily schedules', 'Route optimization'],
                    'points': 5
                },
                'PM-CAP-7.3': {
                    'name': 'Sample tracking',
                    'stories': ['Sample collection', 'Chain of custody', 'Sample management'],
                    'points': 3
                },
                'PM-CAP-7.4': {
                    'name': 'Lab integration',
                    'stories': ['Lab systems', 'Result retrieval', 'Result notifications'],
                    'points': 5
                },
                'PM-CAP-7.5': {
                    'name': 'Home services',
                    'stories': ['Home visits', 'Service coordination', 'Supply management'],
                    'points': 3
                }
            }
        },
        'PM-EPIC-08': {
            'name': 'Clinical Services & Documentation',
            'system': 'Patient Management',
            'complexity': 'High',
            'capabilities': {
                'PM-CAP-8.1': {
                    'name': 'Clinical documentation',
                    'stories': ['Document encounters', 'Clinical notes', 'Record sharing'],
                    'points': 5
                },
                'PM-CAP-8.2': {
                    'name': 'Medication records',
                    'stories': ['MAR documentation', 'Administration tracking', 'Medication history'],
                    'points': 5
                },
                'PM-CAP-8.3': {
                    'name': 'Vital signs',
                    'stories': ['Record vitals', 'Monitoring data', 'Trend analysis'],
                    'points': 3
                },
                'PM-CAP-8.4': {
                    'name': 'Lab results',
                    'stories': ['Order lab tests', 'View results', 'Result trending'],
                    'points': 5
                },
                'PM-CAP-8.5': {
                    'name': 'Adverse events',
                    'stories': ['Report events', 'Clinical alerts', 'Safety monitoring'],
                    'points': 5
                }
            }
        },
        'PM-EPIC-09': {
            'name': 'Delivery to Patients & Hospitals',
            'system': 'Patient Management',
            'complexity': 'Medium',
            'capabilities': {
                'PM-CAP-9.1': {
                    'name': 'Patient delivery',
                    'stories': ['Home delivery scheduling', 'Delivery tracking', 'Delivery preferences'],
                    'points': 3
                },
                'PM-CAP-9.2': {
                    'name': 'Hospital delivery',
                    'stories': ['Hospital coordination', 'Bulk deliveries', 'Ward deliveries'],
                    'points': 3
                },
                'PM-CAP-9.3': {
                    'name': 'Temperature control',
                    'stories': ['Cold chain', 'Temperature monitoring', 'Compliance'],
                    'points': 5
                },
                'PM-CAP-9.4': {
                    'name': 'Verification',
                    'stories': ['Signature capture', 'Identity verification', 'Delivery confirmation'],
                    'points': 3
                },
                'PM-CAP-9.5': {
                    'name': 'Returns management',
                    'stories': ['Returns processing', 'Waste management', 'Destruction records'],
                    'points': 3
                }
            }
        },
        'PM-EPIC-10': {
            'name': 'Compliance & Quality Management',
            'system': 'Patient Management',
            'complexity': 'High',
            'capabilities': {
                'PM-CAP-10.1': {
                    'name': 'GDPR compliance',
                    'stories': ['GDPR tools', 'Data privacy', 'Rights management'],
                    'points': 5
                },
                'PM-CAP-10.2': {
                    'name': 'GDP compliance',
                    'stories': ['GDP tracking', 'Distribution standards', 'Quality assurance'],
                    'points': 5
                },
                'PM-CAP-10.3': {
                    'name': 'Audit trails',
                    'stories': ['Complete auditing', 'Data retention', 'Audit reports'],
                    'points': 5
                },
                'PM-CAP-10.4': {
                    'name': 'Quality metrics',
                    'stories': ['KPI monitoring', 'Quality dashboards', 'Performance tracking'],
                    'points': 3
                },
                'PM-CAP-10.5': {
                    'name': 'Regulatory reporting',
                    'stories': ['Regulatory submissions', 'Compliance reports', 'Incident reporting'],
                    'points': 5
                }
            }
        },
        'PM-EPIC-11': {
            'name': 'Patient Portal & Engagement',
            'system': 'Patient Management',
            'complexity': 'Medium',
            'capabilities': {
                'PM-CAP-11.1': {
                    'name': 'Portal access',
                    'stories': ['Patient login', 'Information access', 'Portal navigation'],
                    'points': 3
                },
                'PM-CAP-11.2': {
                    'name': 'Reminders',
                    'stories': ['Appointment reminders', 'Medication alerts', 'Refill reminders'],
                    'points': 3
                },
                'PM-CAP-11.3': {
                    'name': 'Communication',
                    'stories': ['Secure messaging', 'Notification preferences', 'Care team contact'],
                    'points': 3
                },
                'PM-CAP-11.4': {
                    'name': 'Feedback',
                    'stories': ['Satisfaction surveys', 'Feedback submission', 'Quality ratings'],
                    'points': 3
                },
                'PM-CAP-11.5': {
                    'name': 'Educational resources',
                    'stories': ['Health education', 'Treatment information', 'Resource library'],
                    'points': 3
                }
            }
        }
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
    
    df_phases = pd.DataFrame(phase_summary)
    
    # Format currency columns
    for col in ['Base Cost', 'Total Cost']:
        df_phases[col] = df_phases[col].apply(lambda x: f"${x:,.0f}")
    
    st.dataframe(df_phases, use_container_width=True)
    
    # Visualizations
    col1, col2 = st.columns(2)
    
    with col1:
        # Cost distribution
        cost_data = [ps for ps in phase_summary]
        fig = px.pie(
            cost_data,
            values=[float(ps['Total Cost'].replace('$', '').replace(',', '')) for ps in cost_data],
            names=[ps['Name'] for ps in cost_data],
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
    
    # Format currency columns for display
    df_cost_display = df_cost.copy()
    for col in ['Base Cost', 'Contingency', 'Total Cost', 'Weekly Burn', 'Cost per Person']:
        df_cost_display[col] = df_cost_display[col].apply(lambda x: f"${x:,.0f}")
    
    st.dataframe(df_cost_display, use_container_width=True)
    
    # Cost visualization
    st.subheader("Cost Distribution Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Cost by phase bar chart
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
        # Weekly burn rate comparison
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
    
    resource_data = []
    
    # Phase 0 Resources
    resource_data.append({
        'Phase': 'Phase 0',
        'Role': 'Head of Technology',
        'Location': 'Onsite',
        'Count': 1,
        'Rate': '$140/hr'
    })
    resource_data.append({
        'Phase': 'Phase 0',
        'Role': 'Senior Technical Architect',
        'Location': 'Onsite',
        'Count': 2,
        'Rate': '$113/hr'
    })
    resource_data.append({
        'Phase': 'Phase 0',
        'Role': 'Business Analyst',
        'Location': 'Onsite',
        'Count': 2,
        'Rate': '$82/hr'
    })
    resource_data.append({
        'Phase': 'Phase 0',
        'Role': 'UI/UX Designer',
        'Location': 'Onsite',
        'Count': 1,
        'Rate': '$82/hr'
    })
    
    # Phase 1 Resources (73 people)
    phase1_resources = {
        'Onsite (16)': [
            ('Senior Technical Architect', 2, '$113/hr'),
            ('Technical Architect', 2, '$103/hr'),
            ('Project Manager', 2, '$103/hr'),
            ('Senior Developer', 3, '$87/hr'),
            ('Team Lead', 2, '$89/hr'),
            ('DevOps Engineer', 2, '$87/hr'),
            ('Business Analyst', 2, '$82/hr'),
            ('Integration Specialist', 1, '$89/hr')
        ],
        'Nearshore (27)': [
            ('Technical Architect', 2, '$68/hr'),
            ('Senior Developer', 4, '$58/hr'),
            ('Mobile Developer', 3, '$58/hr'),
            ('Developer', 6, '$54/hr'),
            ('Senior Tester', 3, '$55/hr'),
            ('Automation Test Lead', 2, '$59/hr'),
            ('UI/UX Developer', 3, '$54/hr'),
            ('DevOps Engineer', 1, '$58/hr'),
            ('Integration Developer', 2, '$58/hr'),
            ('Performance Engineer', 1, '$58/hr')
        ],
        'Offshore (30)': [
            ('Senior Developer', 4, '$23/hr'),
            ('Developer', 8, '$21/hr'),
            ('Junior Developer', 4, '$19/hr'),
            ('Integration Developer', 3, '$23/hr'),
            ('Tester', 6, '$20/hr'),
            ('Automation Tester', 3, '$22/hr'),
            ('Performance Tester', 2, '$22/hr')
        ]
    }
    
    # Phase 2 Resources (28 people)
    phase2_resources = {
        'Onsite (7)': [
            ('Technical Architect', 1, '$103/hr'),
            ('Project Manager', 1, '$103/hr'),
            ('Senior Developer', 2, '$87/hr'),
            ('Team Lead', 1, '$89/hr'),
            ('Business Analyst', 1, '$82/hr'),
            ('Data Architect', 1, '$103/hr')
        ],
        'Nearshore (10)': [
            ('Senior Developer', 2, '$58/hr'),
            ('Developer', 3, '$54/hr'),
            ('Senior Tester', 1, '$55/hr'),
            ('Automation Test Lead', 1, '$59/hr'),
            ('UI/UX Developer', 2, '$54/hr'),
            ('QA Lead', 1, '$55/hr')
        ],
        'Offshore (11)': [
            ('Developer', 4, '$21/hr'),
            ('Junior Developer', 2, '$19/hr'),
            ('Tester', 3, '$20/hr'),
            ('Automation Tester', 1, '$22/hr'),
            ('Technical Writer', 1, '$19/hr')
        ]
    }
    
    # Display resources by phase
    phase_select = st.selectbox("Select Phase", ["Phase 0", "Phase 1", "Phase 2"])
    
    if phase_select == "Phase 0":
        df_resources = pd.DataFrame([r for r in resource_data if r['Phase'] == 'Phase 0'])
        st.dataframe(df_resources, use_container_width=True)
        
    elif phase_select == "Phase 1":
        st.write("**Total Team: 73 people**")
        
        for location, resources in phase1_resources.items():
            st.markdown(f"**{location}**")
            for role, count, rate in resources:
                st.write(f"• {role}: {count} @ {rate}")
        
    else:  # Phase 2
        st.write("**Total Team: 28 people**")
        
        for location, resources in phase2_resources.items():
            st.markdown(f"**{location}**")
            for role, count, rate in resources:
                st.write(f"• {role}: {count} @ {rate}")

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
