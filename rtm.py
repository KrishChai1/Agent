import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
from io import BytesIO
import numpy as np

# Page configuration
st.set_page_config(
    page_title="SPLUS RTM Modernization Dashboard",
    page_icon="K",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
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
    }
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        border: 1px solid #cccccc;
        padding: 5px 15px;
        border-radius: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize comprehensive user stories data structure
def initialize_user_stories_data():
    return {
        'EPIC-001': {
            'name': 'Customer Account Management',
            'priority': 'P0',
            'phase': 1,
            'complexity': 'High',
            'capabilities': {
                'C1.1': {
                    'name': 'Account Lifecycle Management',
                    'stories': [
                        {'id': 'US-001.1.1', 'title': 'Create customer accounts with all attributes', 'points': 13},
                        {'id': 'US-001.1.2', 'title': 'Configure integrated/non-integrated warehouse settings', 'points': 8},
                        {'id': 'US-001.1.3', 'title': 'Search accounts by number, company, location', 'points': 5},
                        {'id': 'US-001.1.4', 'title': 'Manage billing details and payment methods', 'points': 8},
                        {'id': 'US-001.1.5', 'title': 'View account dashboard with order metrics', 'points': 13}
                    ]
                },
                'C1.2': {
                    'name': 'User & Role Administration',
                    'stories': [
                        {'id': 'US-001.2.1', 'title': 'Create/edit/delete users with email validation', 'points': 13},
                        {'id': 'US-001.2.2', 'title': 'Assign roles (Order Entry, Inventory, Account Editor)', 'points': 8},
                        {'id': 'US-001.2.3', 'title': 'Configure account-level permissions matrix', 'points': 13},
                        {'id': 'US-001.2.4', 'title': 'Bulk import/export users via CSV', 'points': 8},
                        {'id': 'US-001.2.5', 'title': 'Enforce password policies and MFA', 'points': 5},
                        {'id': 'US-001.2.6', 'title': 'Track login/logout events and permission changes', 'points': 8}
                    ]
                },
                'C1.3': {
                    'name': 'Affiliate & Branch Management',
                    'stories': [
                        {'id': 'US-001.3.1', 'title': 'Manage UPS affiliate agreements', 'points': 8},
                        {'id': 'US-001.3.2', 'title': 'Create and manage affiliate regions', 'points': 5},
                        {'id': 'US-001.3.3', 'title': 'Configure revenue branches', 'points': 8},
                        {'id': 'US-001.3.4', 'title': 'Search affiliated partners by service', 'points': 13},
                        {'id': 'US-001.3.5', 'title': 'Manage branch enable/disable status', 'points': 5}
                    ]
                },
                'C1.4': {
                    'name': 'Account Configuration',
                    'stories': [
                        {'id': 'US-001.4.1', 'title': 'Configure backorder preferences', 'points': 8},
                        {'id': 'US-001.4.2', 'title': 'Set account-specific routing profiles', 'points': 13},
                        {'id': 'US-001.4.3', 'title': 'Configure pick/pack profiles', 'points': 8},
                        {'id': 'US-001.4.4', 'title': 'Set shipping restrictions', 'points': 5},
                        {'id': 'US-001.4.5', 'title': 'Manage notification preferences', 'points': 5}
                    ]
                },
                'C1.5': {
                    'name': 'Customer Portal (CFW)',
                    'stories': [
                        {'id': 'US-001.5.1', 'title': 'Access CFW portal with SSO', 'points': 13},
                        {'id': 'US-001.5.2', 'title': 'Update company contact information', 'points': 5},
                        {'id': 'US-001.5.3', 'title': 'View contract terms and agreements', 'points': 8},
                        {'id': 'US-001.5.4', 'title': 'Download account documents', 'points': 5}
                    ]
                }
            }
        },
        'EPIC-002': {
            'name': 'Order Management & Processing',
            'priority': 'P0',
            'phase': 2,
            'complexity': 'Very High',
            'capabilities': {
                'C2.1': {
                    'name': 'Order Creation & Validation',
                    'stories': [
                        {'id': 'US-002.1.1', 'title': 'Create Inventory Orders for PS', 'points': 21},
                        {'id': 'US-002.1.2', 'title': 'Create Transportation Item Orders', 'points': 13},
                        {'id': 'US-002.1.3', 'title': 'Create Pure Transportation Orders', 'points': 13},
                        {'id': 'US-002.1.4', 'title': 'Order wizard workflow', 'points': 21},
                        {'id': 'US-002.1.5', 'title': 'Real-time order validation', 'points': 13},
                        {'id': 'US-002.1.6', 'title': 'Save draft orders', 'points': 8},
                        {'id': 'US-002.1.7', 'title': 'Clone existing orders', 'points': 5}
                    ]
                },
                'C2.2': {
                    'name': 'Activity Board Management',
                    'stories': [
                        {'id': 'US-002.2.1', 'title': 'View orders with color-coded alarms', 'points': 13},
                        {'id': 'US-002.2.2', 'title': 'Filter Activity Board', 'points': 8},
                        {'id': 'US-002.2.3', 'title': 'Save filter preferences', 'points': 5},
                        {'id': 'US-002.2.4', 'title': 'Bulk actions on orders', 'points': 8},
                        {'id': 'US-002.2.5', 'title': 'Real-time updates via WebSocket', 'points': 13},
                        {'id': 'US-002.2.6', 'title': 'Export to Excel', 'points': 5}
                    ]
                },
                'C2.3': {
                    'name': 'Review Board Workflow',
                    'stories': [
                        {'id': 'US-002.3.1', 'title': 'View orders with violations', 'points': 8},
                        {'id': 'US-002.3.2', 'title': 'Approve/reject with comments', 'points': 8},
                        {'id': 'US-002.3.3', 'title': 'Configure review rules', 'points': 13},
                        {'id': 'US-002.3.4', 'title': 'Set approval hierarchies', 'points': 8},
                        {'id': 'US-002.3.5', 'title': 'Maintain audit trail', 'points': 5},
                        {'id': 'US-002.3.6', 'title': 'Monitor Review Board metrics', 'points': 8}
                    ]
                },
                'C2.4': {
                    'name': 'Order Search & Tracking',
                    'stories': [
                        {'id': 'US-002.4.1', 'title': 'Search orders by criteria', 'points': 8},
                        {'id': 'US-002.4.2', 'title': 'Real-time order tracking', 'points': 13},
                        {'id': 'US-002.4.3', 'title': 'View order history', 'points': 5},
                        {'id': 'US-002.4.4', 'title': 'PS/EC visibility', 'points': 8}
                    ]
                },
                'C2.5': {
                    'name': 'Recurring Orders',
                    'stories': [
                        {'id': 'US-002.5.1', 'title': 'Create recurring templates', 'points': 13},
                        {'id': 'US-002.5.2', 'title': 'Auto-generate scheduled orders', 'points': 13},
                        {'id': 'US-002.5.3', 'title': 'Modify/cancel recurring orders', 'points': 8}
                    ]
                }
            }
        },
        'EPIC-003': {
            'name': 'Inventory Management System',
            'priority': 'P0',
            'phase': 2,
            'complexity': 'Very High',
            'capabilities': {
                'C3.1': {
                    'name': 'Real-time Inventory Tracking',
                    'stories': [
                        {'id': 'US-003.1.1', 'title': 'Summary search with wildcards', 'points': 8},
                        {'id': 'US-003.1.2', 'title': 'Detail search by lot/serial', 'points': 8},
                        {'id': 'US-003.1.3', 'title': 'Display quantities', 'points': 13},
                        {'id': 'US-003.1.4', 'title': 'View substitute items', 'points': 8},
                        {'id': 'US-003.1.5', 'title': 'Response time < 2 seconds', 'points': 21}
                    ]
                },
                'C3.2': {
                    'name': 'Reservation Management',
                    'stories': [
                        {'id': 'US-003.2.1', 'title': 'Auto-reserve on order', 'points': 13},
                        {'id': 'US-003.2.2', 'title': 'View reservations', 'points': 8},
                        {'id': 'US-003.2.3', 'title': 'Manage expiry timeouts', 'points': 5},
                        {'id': 'US-003.2.4', 'title': 'Release on cancellation', 'points': 8},
                        {'id': 'US-003.2.5', 'title': 'Transfer between warehouses', 'points': 13},
                        {'id': 'US-003.2.6', 'title': 'Prevent overselling', 'points': 13}
                    ]
                },
                'C3.3': {
                    'name': 'IMS Integration',
                    'stories': [
                        {'id': 'US-003.3.1', 'title': 'Real-time IMS sync', 'points': 21},
                        {'id': 'US-003.3.2', 'title': 'Cache in Redis', 'points': 13},
                        {'id': 'US-003.3.3', 'title': 'Handle IMS downtime', 'points': 13},
                        {'id': 'US-003.3.4', 'title': 'Reconciliation process', 'points': 8},
                        {'id': 'US-003.3.5', 'title': 'Receive update events', 'points': 13}
                    ]
                },
                'C3.4': {
                    'name': 'Backorder Processing',
                    'stories': [
                        {'id': 'US-003.4.1', 'title': 'Check backorder config', 'points': 8},
                        {'id': 'US-003.4.2', 'title': 'Create backorders', 'points': 13},
                        {'id': 'US-003.4.3', 'title': 'Send notifications', 'points': 8},
                        {'id': 'US-003.4.4', 'title': 'Auto-fulfill on availability', 'points': 13},
                        {'id': 'US-003.4.5', 'title': 'Priority queue management', 'points': 8}
                    ]
                }
            }
        },
        'EPIC-004': {
            'name': 'Routing & Transportation Engine',
            'priority': 'P0',
            'phase': 3,
            'complexity': 'Very High',
            'capabilities': {
                'C4.1': {
                    'name': 'MORO Integration',
                    'stories': [
                        {'id': 'US-004.1.1', 'title': 'Send data to MORO', 'points': 21},
                        {'id': 'US-004.1.2', 'title': 'Receive route options', 'points': 13},
                        {'id': 'US-004.1.3', 'title': 'Calculate using postal codes', 'points': 8},
                        {'id': 'US-004.1.4', 'title': 'Consider package dimensions', 'points': 8},
                        {'id': 'US-004.1.5', 'title': 'TNT WebServices fallback', 'points': 13},
                        {'id': 'US-004.1.6', 'title': 'Manual route override', 'points': 5}
                    ]
                },
                'C4.2': {
                    'name': 'Multi-modal Transportation',
                    'stories': [
                        {'id': 'US-004.2.1', 'title': 'Support air/ground/ocean', 'points': 13},
                        {'id': 'US-004.2.2', 'title': 'Mode selection rules', 'points': 8},
                        {'id': 'US-004.2.3', 'title': 'Multi-leg routes', 'points': 21},
                        {'id': 'US-004.2.4', 'title': 'Cost/time per mode', 'points': 5}
                    ]
                },
                'C4.3': {
                    'name': 'Next Flight Out',
                    'stories': [
                        {'id': 'US-004.3.1', 'title': 'Manage airline codes', 'points': 8},
                        {'id': 'US-004.3.2', 'title': 'Configure airports', 'points': 8},
                        {'id': 'US-004.3.3', 'title': 'SSIM integration', 'points': 13},
                        {'id': 'US-004.3.4', 'title': 'TFS integration', 'points': 13},
                        {'id': 'US-004.3.5', 'title': 'Invalid flight ranges', 'points': 5},
                        {'id': 'US-004.3.6', 'title': 'Flight alerts', 'points': 8}
                    ]
                },
                'C4.4': {
                    'name': 'Carrier Integration',
                    'stories': [
                        {'id': 'US-004.4.1', 'title': 'UPS Quantum View', 'points': 13},
                        {'id': 'US-004.4.2', 'title': 'FedEx via EasyPost', 'points': 13},
                        {'id': 'US-004.4.3', 'title': 'TNT direct integration', 'points': 13},
                        {'id': 'US-004.4.4', 'title': 'Greyhound services', 'points': 8},
                        {'id': 'US-004.4.5', 'title': 'Rate shopping', 'points': 13}
                    ]
                }
            }
        },
        'EPIC-005': {
            'name': 'Vendor & Driver Management',
            'priority': 'P1',
            'phase': 4,
            'complexity': 'High',
            'capabilities': {
                'C5.1': {
                    'name': 'Vendor Lifecycle',
                    'stories': [
                        {'id': 'US-005.1.1', 'title': 'Register vendors', 'points': 13},
                        {'id': 'US-005.1.2', 'title': 'Update vendor info', 'points': 8},
                        {'id': 'US-005.1.3', 'title': 'Manage contracts', 'points': 8},
                        {'id': 'US-005.1.4', 'title': 'Track performance', 'points': 13},
                        {'id': 'US-005.1.5', 'title': 'Search vendors', 'points': 5},
                        {'id': 'US-005.1.6', 'title': 'Activate/deactivate', 'points': 5}
                    ]
                },
                'C5.2': {
                    'name': 'Driver Operations',
                    'stories': [
                        {'id': 'US-005.2.1', 'title': 'Mobile notifications', 'points': 13},
                        {'id': 'US-005.2.2', 'title': 'Accept/reject jobs', 'points': 8},
                        {'id': 'US-005.2.3', 'title': 'View job details', 'points': 8},
                        {'id': 'US-005.2.4', 'title': 'Update milestones', 'points': 13},
                        {'id': 'US-005.2.5', 'title': 'Offline capability', 'points': 21},
                        {'id': 'US-005.2.6', 'title': 'Real-time tracking', 'points': 13}
                    ]
                },
                'C5.3': {
                    'name': 'Job Assignment',
                    'stories': [
                        {'id': 'US-005.3.1', 'title': 'View driver status', 'points': 8},
                        {'id': 'US-005.3.2', 'title': 'Match skills to jobs', 'points': 13},
                        {'id': 'US-005.3.3', 'title': 'Bulk assignments', 'points': 8},
                        {'id': 'US-005.3.4', 'title': 'Reassign jobs', 'points': 5},
                        {'id': 'US-005.3.5', 'title': 'Auto-assign by proximity', 'points': 21}
                    ]
                },
                'C5.4': {
                    'name': 'POD Management',
                    'stories': [
                        {'id': 'US-005.4.1', 'title': 'Capture signature', 'points': 8},
                        {'id': 'US-005.4.2', 'title': 'Capture photo', 'points': 8},
                        {'id': 'US-005.4.3', 'title': 'Validate POD', 'points': 5},
                        {'id': 'US-005.4.4', 'title': 'Send notifications', 'points': 5},
                        {'id': 'US-005.4.5', 'title': 'Store for compliance', 'points': 8}
                    ]
                }
            }
        },
        'EPIC-006': {
            'name': 'Billing & Financial Management',
            'priority': 'P1',
            'phase': 5,
            'complexity': 'High',
            'capabilities': {
                'C6.1': {
                    'name': 'Rate Management',
                    'stories': [
                        {'id': 'US-006.1.1', 'title': 'Create revenue rates', 'points': 13},
                        {'id': 'US-006.1.2', 'title': 'Create cost rates', 'points': 13},
                        {'id': 'US-006.1.3', 'title': 'Rating attributes', 'points': 8},
                        {'id': 'US-006.1.4', 'title': 'Service associations', 'points': 8},
                        {'id': 'US-006.1.5', 'title': 'Effective dates', 'points': 8},
                        {'id': 'US-006.1.6', 'title': 'Rate simulation', 'points': 13}
                    ]
                },
                'C6.2': {
                    'name': 'Billing Review',
                    'stories': [
                        {'id': 'US-006.2.1', 'title': 'Search by status', 'points': 8},
                        {'id': 'US-006.2.2', 'title': 'View cost details', 'points': 5},
                        {'id': 'US-006.2.3', 'title': 'Compare quoted/actual', 'points': 8},
                        {'id': 'US-006.2.4', 'title': 'Edit failed billing', 'points': 13},
                        {'id': 'US-006.2.5', 'title': 'Bulk resubmission', 'points': 8},
                        {'id': 'US-006.2.6', 'title': 'Exception reporting', 'points': 8}
                    ]
                },
                'C6.3': {
                    'name': 'Storage Billing',
                    'stories': [
                        {'id': 'US-006.3.1', 'title': 'Configure accounts', 'points': 8},
                        {'id': 'US-006.3.2', 'title': 'Set frequency', 'points': 5},
                        {'id': 'US-006.3.3', 'title': 'Calculate by UOM', 'points': 13},
                        {'id': 'US-006.3.4', 'title': 'Generate invoices', 'points': 13},
                        {'id': 'US-006.3.5', 'title': 'GBS integration', 'points': 13}
                    ]
                },
                'C6.4': {
                    'name': 'Accrual Processing',
                    'stories': [
                        {'id': 'US-006.4.1', 'title': 'Run extracts', 'points': 8},
                        {'id': 'US-006.4.2', 'title': 'Cost accruals', 'points': 13},
                        {'id': 'US-006.4.3', 'title': 'Revenue accruals', 'points': 13},
                        {'id': 'US-006.4.4', 'title': 'History reports', 'points': 5},
                        {'id': 'US-006.4.5', 'title': 'Settlement processing', 'points': 21}
                    ]
                }
            }
        },
        'EPIC-007': {
            'name': 'Integration Platform',
            'priority': 'P0',
            'phase': 2,
            'complexity': 'Very High',
            'capabilities': {
                'C7.1': {
                    'name': 'GIC/A2A Integration',
                    'stories': [
                        {'id': 'US-007.1.1', 'title': 'Receive XML from GIC', 'points': 13},
                        {'id': 'US-007.1.2', 'title': 'A2A transformation', 'points': 21},
                        {'id': 'US-007.1.3', 'title': 'Publish events', 'points': 13},
                        {'id': 'US-007.1.4', 'title': 'Status updates', 'points': 8},
                        {'id': 'US-007.1.5', 'title': 'Audit trail', 'points': 8},
                        {'id': 'US-007.1.6', 'title': 'Retry mechanisms', 'points': 13}
                    ]
                },
                'C7.2': {
                    'name': 'B2B Processing',
                    'stories': [
                        {'id': 'US-007.2.1', 'title': '90% B2B automation', 'points': 21},
                        {'id': 'US-007.2.2', 'title': 'Customer XML formats', 'points': 13},
                        {'id': 'US-007.2.3', 'title': 'Validate orders', 'points': 13},
                        {'id': 'US-007.2.4', 'title': 'Queue processing', 'points': 8},
                        {'id': 'US-007.2.5', 'title': 'Acknowledgments', 'points': 8}
                    ]
                },
                'C7.3': {
                    'name': 'EDI Management',
                    'stories': [
                        {'id': 'US-007.3.1', 'title': 'Generate EDI', 'points': 13},
                        {'id': 'US-007.3.2', 'title': 'Route via A2A', 'points': 8},
                        {'id': 'US-007.3.3', 'title': 'Customer formats', 'points': 13},
                        {'id': 'US-007.3.4', 'title': 'Handle failures', 'points': 8},
                        {'id': 'US-007.3.5', 'title': 'Audit logs', 'points': 5}
                    ]
                },
                'C7.4': {
                    'name': 'WMS Integration',
                    'stories': [
                        {'id': 'US-007.4.1', 'title': 'Send fulfillment requests', 'points': 13},
                        {'id': 'US-007.4.2', 'title': 'Receive updates', 'points': 13},
                        {'id': 'US-007.4.3', 'title': 'Track operations', 'points': 8},
                        {'id': 'US-007.4.4', 'title': 'Handle exceptions', 'points': 8},
                        {'id': 'US-007.4.5', 'title': 'Multiple instances', 'points': 13}
                    ]
                }
            }
        },
        'EPIC-008': {
            'name': 'Notification & Communication',
            'priority': 'P1',
            'phase': 6,
            'complexity': 'Medium',
            'capabilities': {
                'C8.1': {
                    'name': 'Event Notifications',
                    'stories': [
                        {'id': 'US-008.1.1', 'title': 'Backorder notifications', 'points': 8},
                        {'id': 'US-008.1.2', 'title': 'Order confirmations', 'points': 5},
                        {'id': 'US-008.1.3', 'title': 'Tracking notifications', 'points': 8},
                        {'id': 'US-008.1.4', 'title': 'Delivery updates', 'points': 8},
                        {'id': 'US-008.1.5', 'title': 'Attempted delivery', 'points': 8},
                        {'id': 'US-008.1.6', 'title': 'Flight alerts', 'points': 8}
                    ]
                },
                'C8.2': {
                    'name': 'Multi-Channel',
                    'stories': [
                        {'id': 'US-008.2.1', 'title': 'SendGrid email', 'points': 8},
                        {'id': 'US-008.2.2', 'title': 'Twilio SMS', 'points': 8},
                        {'id': 'US-008.2.3', 'title': 'Push notifications', 'points': 13},
                        {'id': 'US-008.2.4', 'title': 'In-app notifications', 'points': 8},
                        {'id': 'US-008.2.5', 'title': 'Channel preferences', 'points': 5},
                        {'id': 'US-008.2.6', 'title': 'Voice notifications', 'points': 13}
                    ]
                }
            }
        },
        'EPIC-009': {
            'name': 'Service & Activity Configuration',
            'priority': 'P2',
            'phase': 7,
            'complexity': 'Medium',
            'capabilities': {
                'C9.1': {
                    'name': 'Service Management',
                    'stories': [
                        {'id': 'US-009.1.1', 'title': 'Create services', 'points': 5},
                        {'id': 'US-009.1.2', 'title': 'Define vendor types', 'points': 8},
                        {'id': 'US-009.1.3', 'title': 'Eligibility criteria', 'points': 8},
                        {'id': 'US-009.1.4', 'title': 'Service pricing', 'points': 13},
                        {'id': 'US-009.1.5', 'title': 'Enable/disable', 'points': 5}
                    ]
                },
                'C9.2': {
                    'name': 'Activity Config',
                    'stories': [
                        {'id': 'US-009.2.1', 'title': 'Add activities', 'points': 8},
                        {'id': 'US-009.2.2', 'title': 'Set sequence', 'points': 13},
                        {'id': 'US-009.2.3', 'title': 'Define attributes', 'points': 8},
                        {'id': 'US-009.2.4', 'title': 'Track completion', 'points': 8},
                        {'id': 'US-009.2.5', 'title': 'Execution rules', 'points': 13}
                    ]
                },
                'C9.3': {
                    'name': 'Alarm Management',
                    'stories': [
                        {'id': 'US-009.3.1', 'title': 'Yellow alarms', 'points': 5},
                        {'id': 'US-009.3.2', 'title': 'Red alarms', 'points': 5},
                        {'id': 'US-009.3.3', 'title': 'Configure alerts', 'points': 8},
                        {'id': 'US-009.3.4', 'title': 'Enable/disable', 'points': 5},
                        {'id': 'US-009.3.5', 'title': 'Monitoring dashboard', 'points': 13}
                    ]
                }
            }
        },
        'EPIC-010': {
            'name': 'Geographic & Location Services',
            'priority': 'P2',
            'phase': 7,
            'complexity': 'Low',
            'capabilities': {
                'C10.1': {
                    'name': 'Geographic Config',
                    'stories': [
                        {'id': 'US-010.1.1', 'title': 'Configure countries', 'points': 8},
                        {'id': 'US-010.1.2', 'title': 'Manage zip codes', 'points': 8},
                        {'id': 'US-010.1.3', 'title': 'Shared zones', 'points': 8},
                        {'id': 'US-010.1.4', 'title': 'Operating hours', 'points': 5},
                        {'id': 'US-010.1.5', 'title': 'Hierarchies', 'points': 13}
                    ]
                },
                'C10.2': {
                    'name': 'PUDO Management',
                    'stories': [
                        {'id': 'US-010.2.1', 'title': 'Create locations', 'points': 8},
                        {'id': 'US-010.2.2', 'title': 'Search PUDO', 'points': 5},
                        {'id': 'US-010.2.3', 'title': 'Validate availability', 'points': 8},
                        {'id': 'US-010.2.4', 'title': 'Operating hours', 'points': 5}
                    ]
                }
            }
        },
        'EPIC-011': {
            'name': 'Platform Infrastructure & Security',
            'priority': 'P0',
            'phase': 0,
            'complexity': 'Very High',
            'capabilities': {
                'C11.1': {
                    'name': 'Cloud Infrastructure',
                    'stories': [
                        {'id': 'US-011.1.1', 'title': 'Azure resource groups', 'points': 13},
                        {'id': 'US-011.1.2', 'title': 'Hub-Spoke networks', 'points': 13},
                        {'id': 'US-011.1.3', 'title': 'Firewall and NSGs', 'points': 8},
                        {'id': 'US-011.1.4', 'title': 'AKS cluster setup', 'points': 21},
                        {'id': 'US-011.1.5', 'title': 'Istio service mesh', 'points': 13}
                    ]
                },
                'C11.2': {
                    'name': 'Security',
                    'stories': [
                        {'id': 'US-011.2.1', 'title': 'Azure AD B2C', 'points': 13},
                        {'id': 'US-011.2.2', 'title': 'Key Vault setup', 'points': 8},
                        {'id': 'US-011.2.3', 'title': 'RBAC policies', 'points': 13},
                        {'id': 'US-011.2.4', 'title': 'Managed identities', 'points': 8},
                        {'id': 'US-011.2.5', 'title': 'Secret rotation', 'points': 8}
                    ]
                },
                'C11.3': {
                    'name': 'DevOps',
                    'stories': [
                        {'id': 'US-011.3.1', 'title': 'CI/CD pipelines', 'points': 21},
                        {'id': 'US-011.3.2', 'title': 'Blue-green deployment', 'points': 13},
                        {'id': 'US-011.3.3', 'title': 'Automated testing', 'points': 13},
                        {'id': 'US-011.3.4', 'title': 'App Insights setup', 'points': 8},
                        {'id': 'US-011.3.5', 'title': 'Distributed tracing', 'points': 8}
                    ]
                }
            }
        },
        'EPIC-012': {
            'name': 'Reporting & Analytics',
            'priority': 'P2',
            'phase': 7,
            'complexity': 'Medium',
            'capabilities': {
                'C12.1': {
                    'name': 'Operational Reports',
                    'stories': [
                        {'id': 'US-012.1.1', 'title': 'Order volume reports', 'points': 8},
                        {'id': 'US-012.1.2', 'title': 'Performance dashboard', 'points': 13},
                        {'id': 'US-012.1.3', 'title': 'SLA compliance', 'points': 8},
                        {'id': 'US-012.1.4', 'title': 'Exception reports', 'points': 8},
                        {'id': 'US-012.1.5', 'title': 'Inventory analysis', 'points': 8}
                    ]
                },
                'C12.2': {
                    'name': 'Financial Analytics',
                    'stories': [
                        {'id': 'US-012.2.1', 'title': 'Revenue analysis', 'points': 13},
                        {'id': 'US-012.2.2', 'title': 'Billing reconciliation', 'points': 8},
                        {'id': 'US-012.2.3', 'title': 'Profitability reports', 'points': 13},
                        {'id': 'US-012.2.4', 'title': 'Variance analysis', 'points': 8},
                        {'id': 'US-012.2.5', 'title': 'Storage analytics', 'points': 8}
                    ]
                }
            }
        },
        'EPIC-NFR': {
            'name': 'Non-Functional Requirements',
            'priority': 'P0',
            'phase': 8,
            'complexity': 'Very High',
            'capabilities': {
                'CNFR.1': {
                    'name': 'Performance',
                    'stories': [
                        {'id': 'US-NFR.1.1', 'title': 'API < 200ms', 'points': 21},
                        {'id': 'US-NFR.1.2', 'title': '10K orders/hour', 'points': 21},
                        {'id': 'US-NFR.1.3', 'title': '1000+ concurrent', 'points': 13},
                        {'id': 'US-NFR.1.4', 'title': 'Page < 2 seconds', 'points': 13}
                    ]
                },
                'CNFR.2': {
                    'name': 'Security',
                    'stories': [
                        {'id': 'US-NFR.2.1', 'title': 'PCI DSS compliance', 'points': 21},
                        {'id': 'US-NFR.2.2', 'title': 'SOC 2 Type II', 'points': 21},
                        {'id': 'US-NFR.2.3', 'title': 'GDPR compliance', 'points': 13},
                        {'id': 'US-NFR.2.4', 'title': 'OWASP Top 10', 'points': 13}
                    ]
                },
                'CNFR.3': {
                    'name': 'Reliability',
                    'stories': [
                        {'id': 'US-NFR.3.1', 'title': '99.95% uptime', 'points': 21},
                        {'id': 'US-NFR.3.2', 'title': 'RTO/RPO targets', 'points': 21},
                        {'id': 'US-NFR.3.3', 'title': 'Multi-region', 'points': 21},
                        {'id': 'US-NFR.3.4', 'title': 'Auto-failover', 'points': 13}
                    ]
                }
            }
        }
    }

# Configuration
PHASES = {
    0: {'name': 'Discovery & Foundation', 'duration': 3, 'base_cost': 384000},
    1: {'name': 'Core Platform & Customer', 'duration': 4, 'base_cost': 768000},
    2: {'name': 'Order & Inventory', 'duration': 4, 'base_cost': 1152000},
    3: {'name': 'Routing & Transportation', 'duration': 4, 'base_cost': 1088000},
    4: {'name': 'Vendor & Driver', 'duration': 3, 'base_cost': 576000},
    5: {'name': 'Billing & Financial', 'duration': 3, 'base_cost': 504000},
    6: {'name': 'Integration & Notifications', 'duration': 2, 'base_cost': 256000},
    7: {'name': 'Advanced Features', 'duration': 2, 'base_cost': 192000},
    8: {'name': 'Testing & Migration', 'duration': 3, 'base_cost': 456000}
}

# Initialize session state
if 'user_stories_data' not in st.session_state:
    st.session_state.user_stories_data = initialize_user_stories_data()

if 'config' not in st.session_state:
    st.session_state.config = {
        'contingency_percent': 20,
        'cost_per_point': 1500,  # Base cost per story point
        'infrastructure_monthly': 23000,
        'program_duration': 24
    }

def calculate_epic_metrics():
    """Calculate metrics for each EPIC"""
    metrics = {}
    for epic_id, epic in st.session_state.user_stories_data.items():
        total_points = 0
        total_stories = 0
        capabilities_count = len(epic['capabilities'])
        
        for cap in epic['capabilities'].values():
            stories = cap['stories']
            total_stories += len(stories)
            total_points += sum(story['points'] for story in stories)
        
        metrics[epic_id] = {
            'name': epic['name'],
            'priority': epic['priority'],
            'phase': epic['phase'],
            'complexity': epic['complexity'],
            'capabilities': capabilities_count,
            'stories': total_stories,
            'points': total_points,
            'estimated_cost': total_points * st.session_state.config['cost_per_point']
        }
    
    return metrics

def calculate_total_cost():
    """Calculate total program cost based on story points"""
    epic_metrics = calculate_epic_metrics()
    
    # Development cost from story points
    total_points = sum(m['points'] for m in epic_metrics.values())
    development_cost = total_points * st.session_state.config['cost_per_point']
    
    # Infrastructure cost
    infrastructure_cost = st.session_state.config['infrastructure_monthly'] * st.session_state.config['program_duration']
    
    # Additional costs
    additional_costs = 445000  # Fixed additional costs
    
    # Calculate contingency
    subtotal = development_cost + infrastructure_cost + additional_costs
    contingency = subtotal * (st.session_state.config['contingency_percent'] / 100)
    
    return {
        'development': development_cost,
        'infrastructure': infrastructure_cost,
        'additional': additional_costs,
        'subtotal': subtotal,
        'contingency': contingency,
        'total': subtotal + contingency,
        'total_points': total_points
    }

def main():
    st.title("SPLUS RTM Platform Modernization Dashboard")
    st.markdown("**Complete Program Management with User Stories**")
    
    # Sidebar navigation
    page = st.sidebar.radio(
        "Navigation",
        ["Executive Overview", "EPICs & User Stories", "Cost Analysis", 
         "Timeline & Planning", "Reports"]
    )
    
    # Display metrics in sidebar
    costs = calculate_total_cost()
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Program Metrics**")
    st.sidebar.metric("Total Investment", f"${costs['total']:,.0f}")
    st.sidebar.metric("Total Story Points", f"{costs['total_points']:,}")
    st.sidebar.metric("EPICs", len(st.session_state.user_stories_data))
    
    if page == "Executive Overview":
        show_executive_overview()
    elif page == "EPICs & User Stories":
        show_epics_user_stories()
    elif page == "Cost Analysis":
        show_cost_analysis()
    elif page == "Timeline & Planning":
        show_timeline_planning()
    elif page == "Reports":
        show_reports()

def show_executive_overview():
    """Executive dashboard"""
    st.header("Executive Overview")
    
    # Calculate metrics
    epic_metrics = calculate_epic_metrics()
    costs = calculate_total_cost()
    
    # Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Investment", f"${costs['total']:,.0f}")
    with col2:
        st.metric("Development Cost", f"${costs['development']:,.0f}")
    with col3:
        st.metric("Story Points", f"{costs['total_points']:,}")
    with col4:
        st.metric("Cost per Point", f"${st.session_state.config['cost_per_point']:,}")
    with col5:
        st.metric("Contingency", f"{st.session_state.config['contingency_percent']}%")
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["EPIC Overview", "Complexity Analysis", "Phase Distribution", "Cost Breakdown"])
    
    with tab1:
        st.subheader("EPIC Summary")
        
        # Create summary dataframe
        summary_data = []
        for epic_id, metrics in epic_metrics.items():
            summary_data.append({
                'EPIC': epic_id,
                'Name': metrics['name'],
                'Priority': metrics['priority'],
                'Complexity': metrics['complexity'],
                'Phase': metrics['phase'],
                'Capabilities': metrics['capabilities'],
                'User Stories': metrics['stories'],
                'Story Points': metrics['points'],
                'Estimated Cost': metrics['estimated_cost']
            })
        
        df_summary = pd.DataFrame(summary_data)
        
        # Display summary table
        st.dataframe(
            df_summary.style.format({
                'Estimated Cost': '${:,.0f}'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Visualizations
        col1, col2 = st.columns(2)
        
        with col1:
            # Story points by EPIC
            fig = px.bar(df_summary, x='EPIC', y='Story Points', 
                        title='Story Points by EPIC',
                        hover_data=['Name', 'Complexity'])
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # User stories by EPIC
            fig = px.bar(df_summary, x='EPIC', y='User Stories',
                        title='User Stories Count by EPIC',
                        hover_data=['Name', 'Capabilities'])
            fig.update_traces(marker_color='lightgreen')
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("Complexity Analysis")
        
        # Complexity distribution
        complexity_dist = df_summary.groupby('Complexity').agg({
            'EPIC': 'count',
            'Story Points': 'sum',
            'User Stories': 'sum'
        }).reset_index()
        complexity_dist.columns = ['Complexity', 'EPICs', 'Story Points', 'User Stories']
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.pie(complexity_dist, values='Story Points', names='Complexity',
                        title='Story Points by Complexity')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.bar(complexity_dist, x='Complexity', y=['EPICs', 'User Stories'],
                        title='Distribution by Complexity', barmode='group')
            st.plotly_chart(fig, use_container_width=True)
        
        # Complexity table
        st.dataframe(complexity_dist, use_container_width=True, hide_index=True)
    
    with tab3:
        st.subheader("Phase Distribution")
        
        # Phase distribution
        phase_dist = df_summary.groupby('Phase').agg({
            'EPIC': 'count',
            'Story Points': 'sum',
            'Estimated Cost': 'sum'
        }).reset_index()
        
        phase_names = {i: PHASES[i]['name'] for i in range(9)}
        phase_dist['Phase Name'] = phase_dist['Phase'].map(phase_names)
        
        # Visualization
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Story Points', x=phase_dist['Phase'], y=phase_dist['Story Points']))
        fig.add_trace(go.Scatter(name='EPICs Count', x=phase_dist['Phase'], y=phase_dist['EPIC'],
                                yaxis='y2', mode='lines+markers', line=dict(width=3)))
        
        fig.update_layout(
            title='Phase-wise Distribution',
            xaxis_title='Phase',
            yaxis_title='Story Points',
            yaxis2=dict(title='Number of EPICs', overlaying='y', side='right'),
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Phase table
        st.dataframe(
            phase_dist[['Phase', 'Phase Name', 'EPIC', 'Story Points', 'Estimated Cost']].rename(
                columns={'EPIC': 'EPICs Count'}
            ).style.format({'Estimated Cost': '${:,.0f}'}),
            use_container_width=True,
            hide_index=True
        )
    
    with tab4:
        st.subheader("Cost Breakdown")
        
        # Cost components
        col1, col2 = st.columns(2)
        
        with col1:
            cost_breakdown = {
                'Development': costs['development'],
                'Infrastructure': costs['infrastructure'],
                'Additional': costs['additional'],
                'Contingency': costs['contingency']
            }
            
            fig = px.pie(values=list(cost_breakdown.values()), 
                        names=list(cost_breakdown.keys()),
                        title='Cost Components')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("**Cost Summary**")
            st.metric("Development", f"${costs['development']:,.0f}")
            st.metric("Infrastructure", f"${costs['infrastructure']:,.0f}")
            st.metric("Additional", f"${costs['additional']:,.0f}")
            st.metric("Contingency", f"${costs['contingency']:,.0f}")
            st.markdown("---")
            st.metric("**TOTAL**", f"${costs['total']:,.0f}")

def show_epics_user_stories():
    """EPICs and User Stories management"""
    st.header("EPICs & User Stories Management")
    
    # Configuration controls - Single source of truth for contingency
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.config['cost_per_point'] = st.number_input(
            "Cost per Story Point ($)",
            min_value=500,
            max_value=3000,
            value=st.session_state.config['cost_per_point'],
            step=100,
            help="Adjust the cost per story point to see impact on total cost"
        )
    with col2:
        # Single contingency slider that updates session state directly
        st.session_state.config['contingency_percent'] = st.slider(
            "Contingency %",
            min_value=10,
            max_value=30,
            value=st.session_state.config['contingency_percent'],
            step=5,
            help="Adjust contingency percentage"
        )
    with col3:
        epic_metrics = calculate_epic_metrics()
        total_points = sum(m['points'] for m in epic_metrics.values())
        st.metric("Total Story Points", f"{total_points:,}")
        st.metric("Estimated Dev Cost", f"${total_points * st.session_state.config['cost_per_point']:,.0f}")
    
    # Show updated total with contingency
    costs = calculate_total_cost()
    st.info(f"**Total Investment with {st.session_state.config['contingency_percent']}% Contingency: ${costs['total']:,.0f}**")
    
    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["EPIC List & Complexity", "EPICs, Capabilities & User Stories", "Edit User Stories"])
    
    with tab1:
        st.subheader("EPIC List with Overall Complexity")
        
        # EPIC overview table
        epic_overview = []
        for epic_id, epic in st.session_state.user_stories_data.items():
            metrics = epic_metrics[epic_id]
            epic_overview.append({
                'EPIC ID': epic_id,
                'EPIC Name': epic['name'],
                'Priority': epic['priority'],
                'Complexity': epic['complexity'],
                'Phase': epic['phase'],
                'Capabilities': metrics['capabilities'],
                'User Stories': metrics['stories'],
                'Story Points': metrics['points'],
                'Estimated Cost': metrics['estimated_cost']
            })
        
        df_epic_overview = pd.DataFrame(epic_overview)
        
        # Editable dataframe for complexity and priority
        edited_df = st.data_editor(
            df_epic_overview,
            column_config={
                "Priority": st.column_config.SelectboxColumn(
                    options=["P0", "P1", "P2"]
                ),
                "Complexity": st.column_config.SelectboxColumn(
                    options=["Low", "Medium", "High", "Very High"]
                ),
                "Phase": st.column_config.NumberColumn(
                    min_value=0,
                    max_value=8
                ),
                "Estimated Cost": st.column_config.NumberColumn(
                    format="$%d",
                    disabled=True
                )
            },
            disabled=["EPIC ID", "EPIC Name", "Capabilities", "User Stories", "Story Points"],
            hide_index=True,
            use_container_width=True
        )
        
        # Update data if changed
        for idx, row in edited_df.iterrows():
            epic_id = row['EPIC ID']
            if epic_id in st.session_state.user_stories_data:
                st.session_state.user_stories_data[epic_id]['priority'] = row['Priority']
                st.session_state.user_stories_data[epic_id]['complexity'] = row['Complexity']
                st.session_state.user_stories_data[epic_id]['phase'] = row['Phase']
        
        # Complexity summary
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        complexity_summary = df_epic_overview.groupby('Complexity')['Story Points'].sum()
        priority_summary = df_epic_overview.groupby('Priority')['Story Points'].sum()
        
        with col1:
            st.markdown("**Complexity Distribution**")
            for comp, points in complexity_summary.items():
                st.write(f"{comp}: {points:,} points")
        
        with col2:
            st.markdown("**Priority Distribution**")
            for pri, points in priority_summary.items():
                st.write(f"{pri}: {points:,} points")
        
        with col3:
            st.markdown("**Phase Summary**")
            phase_summary = df_epic_overview.groupby('Phase')['Story Points'].sum()
            for phase, points in phase_summary.items():
                st.write(f"Phase {phase}: {points:,} points")
    
    with tab2:
        st.subheader("EPICs, Capabilities and User Stories")
        
        # Select EPIC to view
        epic_id = st.selectbox(
            "Select EPIC",
            options=list(st.session_state.user_stories_data.keys()),
            format_func=lambda x: f"{x}: {st.session_state.user_stories_data[x]['name']}"
        )
        
        if epic_id:
            epic = st.session_state.user_stories_data[epic_id]
            
            # EPIC info
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Priority", epic['priority'])
            with col2:
                st.metric("Complexity", epic['complexity'])
            with col3:
                st.metric("Phase", epic['phase'])
            with col4:
                epic_total_points = sum(
                    sum(story['points'] for story in cap['stories'])
                    for cap in epic['capabilities'].values()
                )
                st.metric("Total Points", epic_total_points)
            
            # Display capabilities and stories
            for cap_id, capability in epic['capabilities'].items():
                with st.expander(f"{cap_id}: {capability['name']} ({len(capability['stories'])} stories)"):
                    # Create dataframe for stories
                    stories_data = []
                    for story in capability['stories']:
                        stories_data.append({
                            'Story ID': story['id'],
                            'Title': story['title'],
                            'Points': story['points']
                        })
                    
                    df_stories = pd.DataFrame(stories_data)
                    
                    # Display stories
                    st.dataframe(df_stories, use_container_width=True, hide_index=True)
                    
                    # Capability summary
                    cap_total_points = df_stories['Points'].sum()
                    st.info(f"**Capability Total:** {len(stories_data)} stories, {cap_total_points} points")
    
    with tab3:
        st.subheader("Edit User Stories")
        
        # Select EPIC and Capability
        col1, col2 = st.columns(2)
        
        with col1:
            edit_epic_id = st.selectbox(
                "Select EPIC to Edit",
                options=list(st.session_state.user_stories_data.keys()),
                format_func=lambda x: f"{x}: {st.session_state.user_stories_data[x]['name']}",
                key="edit_epic"
            )
        
        with col2:
            if edit_epic_id:
                capabilities = list(st.session_state.user_stories_data[edit_epic_id]['capabilities'].keys())
                edit_cap_id = st.selectbox(
                    "Select Capability",
                    options=capabilities,
                    format_func=lambda x: f"{x}: {st.session_state.user_stories_data[edit_epic_id]['capabilities'][x]['name']}",
                    key="edit_cap"
                )
        
        if edit_epic_id and edit_cap_id:
            # Get current stories
            current_stories = st.session_state.user_stories_data[edit_epic_id]['capabilities'][edit_cap_id]['stories']
            
            # Create editable dataframe
            df_edit_stories = pd.DataFrame(current_stories)
            
            edited_stories = st.data_editor(
                df_edit_stories,
                column_config={
                    "points": st.column_config.NumberColumn(
                        "Story Points",
                        min_value=1,
                        max_value=40,
                        step=1
                    )
                },
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True
            )
            
            # Update stories
            if st.button("Save Changes"):
                st.session_state.user_stories_data[edit_epic_id]['capabilities'][edit_cap_id]['stories'] = edited_stories.to_dict('records')
                st.success("User stories updated successfully!")
                st.rerun()
            
            # Show impact
            original_points = sum(story['points'] for story in current_stories)
            new_points = edited_stories['points'].sum() if not edited_stories.empty else 0
            difference = new_points - original_points
            
            if difference != 0:
                st.warning(f"Point difference: {difference:+d} (Original: {original_points}, New: {new_points})")
                cost_impact = difference * st.session_state.config['cost_per_point']
                st.info(f"Cost impact: ${cost_impact:+,.0f}")

def show_cost_analysis():
    """Cost Analysis page"""
    st.header("Cost Analysis")
    
    # Calculate costs
    costs = calculate_total_cost()
    epic_metrics = calculate_epic_metrics()
    
    # Cost controls - Use session state values directly
    col1, col2 = st.columns(2)
    
    with col1:
        # Contingency adjustment that updates session state
        st.session_state.config['contingency_percent'] = st.slider(
            "Adjust Contingency %",
            min_value=10,
            max_value=30,
            value=st.session_state.config['contingency_percent'],
            step=5,
            key="cost_contingency",
            help="Changes here will affect total cost immediately"
        )
    
    with col2:
        st.session_state.config['cost_per_point'] = st.number_input(
            "Cost per Story Point ($)",
            min_value=500,
            max_value=3000,
            value=st.session_state.config['cost_per_point'],
            step=100,
            key="cost_per_point_slider"
        )
    
    # Recalculate costs after any changes
    costs = calculate_total_cost()
    
    # Display updated total
    st.success(f"**Updated Total Investment: ${costs['total']:,.0f}** (with {st.session_state.config['contingency_percent']}% contingency)")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Phase-wise Cost", "EPIC-wise Cost", "Story Point Analysis", "TCO"])
    
    with tab1:
        st.subheader("Phase-wise Cost Distribution")
        
        # Calculate phase costs
        phase_costs = []
        for phase_id, phase_info in PHASES.items():
            phase_epics = [eid for eid, e in st.session_state.user_stories_data.items() if e['phase'] == phase_id]
            phase_points = sum(epic_metrics[eid]['points'] for eid in phase_epics if eid in epic_metrics)
            phase_cost = phase_points * st.session_state.config['cost_per_point']
            
            phase_costs.append({
                'Phase': phase_id,
                'Name': phase_info['name'],
                'Duration': phase_info['duration'],
                'EPICs': len(phase_epics),
                'Story Points': phase_points,
                'Development Cost': phase_cost,
                'Base Cost': phase_info['base_cost'],
                'Total Cost': max(phase_cost, phase_info['base_cost'])
            })
        
        df_phase_costs = pd.DataFrame(phase_costs)
        
        # Display table
        st.dataframe(
            df_phase_costs.style.format({
                'Development Cost': '${:,.0f}',
                'Base Cost': '${:,.0f}',
                'Total Cost': '${:,.0f}'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Visualization
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Story Point Cost', x=df_phase_costs['Phase'], 
                            y=df_phase_costs['Development Cost']))
        fig.add_trace(go.Bar(name='Base Cost', x=df_phase_costs['Phase'], 
                            y=df_phase_costs['Base Cost']))
        fig.update_layout(
            title='Phase Cost Comparison',
            xaxis_title='Phase',
            yaxis_title='Cost ($)',
            barmode='group'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("EPIC-wise Cost Analysis")
        
        # EPIC cost table
        epic_cost_data = []
        for epic_id, metrics in epic_metrics.items():
            epic_cost_data.append({
                'EPIC': epic_id,
                'Name': metrics['name'],
                'Priority': metrics['priority'],
                'Complexity': metrics['complexity'],
                'Story Points': metrics['points'],
                'Cost': metrics['estimated_cost'],
                'Percentage': (metrics['estimated_cost'] / costs['development'] * 100) if costs['development'] > 0 else 0
            })
        
        df_epic_costs = pd.DataFrame(epic_cost_data)
        df_epic_costs = df_epic_costs.sort_values('Cost', ascending=False)
        
        # Display table
        st.dataframe(
            df_epic_costs.style.format({
                'Cost': '${:,.0f}',
                'Percentage': '{:.1f}%'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Visualization
        fig = px.treemap(
            df_epic_costs,
            path=['Priority', 'EPIC'],
            values='Cost',
            title='EPIC Cost Distribution by Priority'
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.subheader("Story Point Analysis")
        
        # Point distribution
        point_ranges = {
            '1-5': 0, '8': 0, '13': 0, '21': 0
        }
        
        for epic in st.session_state.user_stories_data.values():
            for cap in epic['capabilities'].values():
                for story in cap['stories']:
                    points = story['points']
                    if points <= 5:
                        point_ranges['1-5'] += 1
                    elif points == 8:
                        point_ranges['8'] += 1
                    elif points == 13:
                        point_ranges['13'] += 1
                    elif points == 21:
                        point_ranges['21'] += 1
        
        # Visualization
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.pie(values=list(point_ranges.values()), 
                        names=list(point_ranges.keys()),
                        title='Story Distribution by Points')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Cost by point size
            point_costs = {}
            for key, count in point_ranges.items():
                if key == '1-5':
                    avg_points = 3
                else:
                    avg_points = int(key)
                point_costs[key] = count * avg_points * st.session_state.config['cost_per_point']
            
            fig = px.bar(x=list(point_costs.keys()), y=list(point_costs.values()),
                        title='Cost by Story Point Size',
                        labels={'x': 'Point Range', 'y': 'Total Cost ($)'})
            st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.subheader("Total Cost of Ownership")
        
        # Refresh costs to ensure latest values
        costs = calculate_total_cost()
        
        # TCO breakdown
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Cost Components**")
            st.metric("Development", f"${costs['development']:,.0f}")
            st.metric("Infrastructure", f"${costs['infrastructure']:,.0f}")
            st.metric("Additional", f"${costs['additional']:,.0f}")
            st.metric(f"Contingency ({st.session_state.config['contingency_percent']}%)", 
                     f"${costs['contingency']:,.0f}")
            st.markdown("---")
            st.metric("**TOTAL**", f"${costs['total']:,.0f}")
        
        with col2:
            # Percentage breakdown
            percentages = {
                'Development': costs['development'] / costs['total'] * 100,
                'Infrastructure': costs['infrastructure'] / costs['total'] * 100,
                'Additional': costs['additional'] / costs['total'] * 100,
                'Contingency': costs['contingency'] / costs['total'] * 100
            }
            
            fig = go.Figure(data=[
                go.Bar(x=list(percentages.keys()), 
                      y=list(percentages.values()),
                      text=[f"{v:.1f}%" for v in percentages.values()],
                      textposition='auto')
            ])
            fig.update_layout(
                title="Cost Component Percentages",
                yaxis_title="Percentage (%)"
            )
            st.plotly_chart(fig, use_container_width=True)

def show_timeline_planning():
    """Timeline and Planning page"""
    st.header("Timeline & Planning")
    
    # Create Gantt data
    gantt_data = []
    start_date = datetime(2024, 1, 1)
    
    for phase_id, phase_info in PHASES.items():
        end_date = start_date + timedelta(days=phase_info['duration'] * 30)
        
        # Get EPICs in this phase
        phase_epics = [eid for eid, e in st.session_state.user_stories_data.items() 
                      if e['phase'] == phase_id]
        
        gantt_data.append({
            'Phase': f"Phase {phase_id}",
            'Name': phase_info['name'],
            'Start': start_date,
            'End': end_date,
            'Duration': f"{phase_info['duration']} months",
            'EPICs': len(phase_epics)
        })
        start_date = end_date
    
    df_gantt = pd.DataFrame(gantt_data)
    
    # Gantt chart
    fig = px.timeline(
        df_gantt,
        x_start="Start",
        x_end="End",
        y="Phase",
        title="24-Month Implementation Timeline",
        hover_data=['Name', 'Duration', 'EPICs']
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)
    
    # Phase details
    st.subheader("Phase Details")
    
    for phase_id, phase_info in PHASES.items():
        phase_epics = [eid for eid, e in st.session_state.user_stories_data.items() 
                      if e['phase'] == phase_id]
        
        with st.expander(f"Phase {phase_id}: {phase_info['name']} ({len(phase_epics)} EPICs)"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Duration", f"{phase_info['duration']} months")
            
            with col2:
                st.metric("Base Cost", f"${phase_info['base_cost']:,.0f}")
            
            with col3:
                epic_metrics = calculate_epic_metrics()
                phase_points = sum(epic_metrics[eid]['points'] for eid in phase_epics 
                                  if eid in epic_metrics)
                st.metric("Story Points", phase_points)
            
            if phase_epics:
                st.markdown("**EPICs in this Phase:**")
                for epic_id in phase_epics:
                    epic = st.session_state.user_stories_data[epic_id]
                    st.write(f"- {epic_id}: {epic['name']} ({epic['priority']}, {epic['complexity']})")

def show_reports():
    """Reports generation"""
    st.header("Reports")
    
    # Report type selection
    report_type = st.selectbox(
        "Select Report Type",
        ["Executive Summary", "User Stories Report", "Cost Analysis Report", "EPIC Details Report"]
    )
    
    if report_type == "Executive Summary":
        generate_executive_summary()
    elif report_type == "User Stories Report":
        generate_stories_report()
    elif report_type == "Cost Analysis Report":
        generate_cost_report()
    elif report_type == "EPIC Details Report":
        generate_epic_report()

def generate_executive_summary():
    """Generate executive summary"""
    st.subheader("Executive Summary Report")
    
    costs = calculate_total_cost()
    epic_metrics = calculate_epic_metrics()
    
    report = f"""
    SPLUS RTM MODERNIZATION - EXECUTIVE SUMMARY
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
    
    PROGRAM OVERVIEW
    - Duration: 24 months
    - Total Investment: ${costs['total']:,.0f}
    - Total Story Points: {costs['total_points']:,}
    - Total EPICs: {len(epic_metrics)}
    - Cost per Point: ${st.session_state.config['cost_per_point']:,}
    
    COST BREAKDOWN
    - Development: ${costs['development']:,.0f}
    - Infrastructure: ${costs['infrastructure']:,.0f}
    - Additional: ${costs['additional']:,.0f}
    - Contingency ({st.session_state.config['contingency_percent']}%): ${costs['contingency']:,.0f}
    
    EPIC SUMMARY
    """
    
    for epic_id, metrics in epic_metrics.items():
        report += f"""
    {epic_id}: {metrics['name']}
    - Priority: {metrics['priority']}
    - Complexity: {metrics['complexity']}
    - Story Points: {metrics['points']}
    - Estimated Cost: ${metrics['estimated_cost']:,.0f}
    """
    
    st.text_area("Report Preview", report, height=400)
    
    st.download_button(
        label="Download Executive Summary",
        data=report,
        file_name=f"RTM_Executive_Summary_{datetime.now().strftime('%Y%m%d')}.txt",
        mime="text/plain"
    )

def generate_stories_report():
    """Generate user stories report"""
    st.subheader("User Stories Report")
    
    stories_data = []
    for epic_id, epic in st.session_state.user_stories_data.items():
        for cap_id, capability in epic['capabilities'].items():
            for story in capability['stories']:
                stories_data.append({
                    'EPIC ID': epic_id,
                    'EPIC Name': epic['name'],
                    'Capability ID': cap_id,
                    'Capability': capability['name'],
                    'Story ID': story['id'],
                    'Story Title': story['title'],
                    'Story Points': story['points'],
                    'Estimated Cost': story['points'] * st.session_state.config['cost_per_point']
                })
    
    df_stories = pd.DataFrame(stories_data)
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Stories", len(df_stories))
    with col2:
        st.metric("Total Points", df_stories['Story Points'].sum())
    with col3:
        st.metric("Total Cost", f"${df_stories['Estimated Cost'].sum():,.0f}")
    
    # Display sample
    st.dataframe(df_stories.head(20), use_container_width=True, hide_index=True)
    
    # Download
    csv = df_stories.to_csv(index=False)
    st.download_button(
        label="Download Complete User Stories Report (CSV)",
        data=csv,
        file_name=f"RTM_User_Stories_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

def generate_cost_report():
    """Generate cost analysis report"""
    st.subheader("Cost Analysis Report")
    
    epic_metrics = calculate_epic_metrics()
    
    # Create cost report data
    cost_data = []
    for epic_id, metrics in epic_metrics.items():
        epic = st.session_state.user_stories_data[epic_id]
        cost_data.append({
            'EPIC': epic_id,
            'Name': metrics['name'],
            'Priority': metrics['priority'],
            'Complexity': metrics['complexity'],
            'Phase': metrics['phase'],
            'Capabilities': metrics['capabilities'],
            'Stories': metrics['stories'],
            'Points': metrics['points'],
            'Cost': metrics['estimated_cost']
        })
    
    df_cost = pd.DataFrame(cost_data)
    
    # Display
    st.dataframe(
        df_cost.style.format({'Cost': '${:,.0f}'}),
        use_container_width=True,
        hide_index=True
    )
    
    # Download
    csv = df_cost.to_csv(index=False)
    st.download_button(
        label="Download Cost Report (CSV)",
        data=csv,
        file_name=f"RTM_Cost_Report_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

def generate_epic_report():
    """Generate detailed EPIC report"""
    st.subheader("EPIC Details Report")
    
    # Select EPIC
    epic_id = st.selectbox(
        "Select EPIC for detailed report",
        options=list(st.session_state.user_stories_data.keys()),
        format_func=lambda x: f"{x}: {st.session_state.user_stories_data[x]['name']}"
    )
    
    if epic_id:
        epic = st.session_state.user_stories_data[epic_id]
        
        report = f"""
        EPIC DETAILS REPORT
        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
        
        EPIC: {epic_id}
        Name: {epic['name']}
        Priority: {epic['priority']}
        Complexity: {epic['complexity']}
        Phase: {epic['phase']}
        
        CAPABILITIES AND USER STORIES
        """
        
        total_points = 0
        for cap_id, capability in epic['capabilities'].items():
            cap_points = sum(story['points'] for story in capability['stories'])
            total_points += cap_points
            
            report += f"""
        
        {cap_id}: {capability['name']}
        Total Stories: {len(capability['stories'])}
        Total Points: {cap_points}
        
        User Stories:
        """
            for story in capability['stories']:
                report += f"""
        - {story['id']}: {story['title']} ({story['points']} points)
        """
        
        report += f"""
        
        SUMMARY
        Total Capabilities: {len(epic['capabilities'])}
        Total User Stories: {sum(len(cap['stories']) for cap in epic['capabilities'].values())}
        Total Story Points: {total_points}
        Estimated Cost: ${total_points * st.session_state.config['cost_per_point']:,.0f}
        """
        
        st.text_area("Report Preview", report, height=400)
        
        st.download_button(
            label=f"Download {epic_id} Report",
            data=report,
            file_name=f"RTM_{epic_id}_Report_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain"
        )

if __name__ == "__main__":
    main()
