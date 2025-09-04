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
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize comprehensive user stories data
def initialize_epics_data():
    return {
        'EPIC-001': {
            'name': 'Customer Account Management',
            'priority': 'P0',
            'phase': 1,
            'capabilities': {
                'C1.1': {
                    'name': 'Account Lifecycle Management',
                    'user_stories': [
                        {'id': 'US-001.1.1', 'title': 'Create customer accounts with all attributes', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-001.1.2', 'title': 'Configure integrated/non-integrated warehouse settings', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-001.1.3', 'title': 'Search accounts by number, company, location', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-001.1.4', 'title': 'Manage billing details and payment methods', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-001.1.5', 'title': 'View account dashboard with order metrics', 'points': 13, 'status': 'Not Started'}
                    ]
                },
                'C1.2': {
                    'name': 'User & Role Administration',
                    'user_stories': [
                        {'id': 'US-001.2.1', 'title': 'Create/edit/delete users with email validation', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-001.2.2', 'title': 'Assign roles (Order Entry, Inventory, Account Editor)', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-001.2.3', 'title': 'Configure account-level permissions matrix', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-001.2.4', 'title': 'Bulk import/export users via CSV', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-001.2.5', 'title': 'Enforce password policies and MFA', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-001.2.6', 'title': 'Track login/logout events and permission changes', 'points': 8, 'status': 'Not Started'}
                    ]
                },
                'C1.3': {
                    'name': 'Affiliate & Branch Management',
                    'user_stories': [
                        {'id': 'US-001.3.1', 'title': 'Manage UPS affiliate agreements with dates', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-001.3.2', 'title': 'Create and manage affiliate regions', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-001.3.3', 'title': 'Configure revenue branches for affiliates', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-001.3.4', 'title': 'Search UPS-affiliated partners by service', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-001.3.5', 'title': 'Manage branch details with enable/disable', 'points': 5, 'status': 'Not Started'}
                    ]
                },
                'C1.4': {
                    'name': 'Account Configuration & Preferences',
                    'user_stories': [
                        {'id': 'US-001.4.1', 'title': 'Configure backorder preferences per account', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-001.4.2', 'title': 'Set account-specific routing profiles', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-001.4.3', 'title': 'Configure pick/pack profiles per service', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-001.4.4', 'title': 'Set shipping restrictions by state/country', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-001.4.5', 'title': 'Manage notification preferences', 'points': 5, 'status': 'Not Started'}
                    ]
                },
                'C1.5': {
                    'name': 'Customer Portal (CFW)',
                    'user_stories': [
                        {'id': 'US-001.5.1', 'title': 'Access CFW portal with SSO', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-001.5.2', 'title': 'Update company contact information', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-001.5.3', 'title': 'View contract terms and agreements', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-001.5.4', 'title': 'Download account documents and reports', 'points': 5, 'status': 'Not Started'}
                    ]
                }
            }
        },
        'EPIC-002': {
            'name': 'Order Management & Processing',
            'priority': 'P0',
            'phase': 2,
            'capabilities': {
                'C2.1': {
                    'name': 'Order Creation & Validation',
                    'user_stories': [
                        {'id': 'US-002.1.1', 'title': 'Create Inventory Orders for PS customers', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-002.1.2', 'title': 'Create Transportation Item Orders', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-002.1.3', 'title': 'Create Pure Transportation Orders for EC', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-002.1.4', 'title': 'Order wizard (Customer→Shipment→Inventory→Route)', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-002.1.5', 'title': 'Real-time order validation against rules', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-002.1.6', 'title': 'Save draft orders and resume later', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-002.1.7', 'title': 'Clone existing orders', 'points': 5, 'status': 'Not Started'}
                    ]
                },
                'C2.2': {
                    'name': 'Activity Board Management',
                    'user_stories': [
                        {'id': 'US-002.2.1', 'title': 'View orders with Green/Yellow/Red alarms', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-002.2.2', 'title': 'Filter Activity Board by multiple criteria', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-002.2.3', 'title': 'Save and reuse filter preferences', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-002.2.4', 'title': 'Bulk actions on filtered orders', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-002.2.5', 'title': 'Real-time updates via SignalR/WebSocket', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-002.2.6', 'title': 'Export Activity Board to Excel', 'points': 5, 'status': 'Not Started'}
                    ]
                },
                'C2.3': {
                    'name': 'Review Board Workflow',
                    'user_stories': [
                        {'id': 'US-002.3.1', 'title': 'View orders with business rule violations', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-002.3.2', 'title': 'Approve/reject orders with comments', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-002.3.3', 'title': 'Configure review rules and thresholds', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-002.3.4', 'title': 'Set approval hierarchies', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-002.3.5', 'title': 'Maintain audit trail of review actions', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-002.3.6', 'title': 'Monitor Review Board metrics', 'points': 8, 'status': 'Not Started'}
                    ]
                },
                'C2.4': {
                    'name': 'Order Search & Tracking',
                    'user_stories': [
                        {'id': 'US-002.4.1', 'title': 'Search orders by multiple criteria', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-002.4.2', 'title': 'Track order status in real-time', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-002.4.3', 'title': 'View complete order history', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-002.4.4', 'title': 'Order visibility across PS and EC instances', 'points': 8, 'status': 'Not Started'}
                    ]
                },
                'C2.5': {
                    'name': 'Recurring Order Management',
                    'user_stories': [
                        {'id': 'US-002.5.1', 'title': 'Create recurring order templates', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-002.5.2', 'title': 'Auto-generate orders based on schedules', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-002.5.3', 'title': 'Modify/cancel recurring orders', 'points': 8, 'status': 'Not Started'}
                    ]
                }
            }
        },
        'EPIC-003': {
            'name': 'Inventory Management System',
            'priority': 'P0',
            'phase': 2,
            'capabilities': {
                'C3.1': {
                    'name': 'Real-time Inventory Tracking',
                    'user_stories': [
                        {'id': 'US-003.1.1', 'title': 'Summary search by item with wildcards', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-003.1.2', 'title': 'Detail search by vendor lot/serial', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-003.1.3', 'title': 'Display available, reserved, on-hand quantities', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-003.1.4', 'title': 'View substitute items when configured', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-003.1.5', 'title': 'Response time < 2 seconds for queries', 'points': 21, 'status': 'Not Started'}
                    ]
                },
                'C3.2': {
                    'name': 'Reservation Management',
                    'user_stories': [
                        {'id': 'US-003.2.1', 'title': 'Auto-reserve inventory on order creation', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-003.2.2', 'title': 'View reservations by warehouse/item', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-003.2.3', 'title': 'Manage reservation expiry timeouts', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-003.2.4', 'title': 'Release reservations on cancellation', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-003.2.5', 'title': 'Transfer reservations between warehouses', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-003.2.6', 'title': 'Prevent overselling with concurrent orders', 'points': 13, 'status': 'Not Started'}
                    ]
                },
                'C3.3': {
                    'name': 'IMS Integration & Sync',
                    'user_stories': [
                        {'id': 'US-003.3.1', 'title': 'Real-time sync with Oracle IMS via REST', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-003.3.2', 'title': 'Cache frequently accessed items in Redis', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-003.3.3', 'title': 'Handle IMS downtime with cached data', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-003.3.4', 'title': 'Reconciliation process for discrepancies', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-003.3.5', 'title': 'Receive inventory update events from IMS', 'points': 13, 'status': 'Not Started'}
                    ]
                },
                'C3.4': {
                    'name': 'Backorder Processing',
                    'user_stories': [
                        {'id': 'US-003.4.1', 'title': 'Check account backorder configuration', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-003.4.2', 'title': 'Create backorders when inventory unavailable', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-003.4.3', 'title': 'Send backorder notifications', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-003.4.4', 'title': 'Auto-fulfill when inventory available', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-003.4.5', 'title': 'Manage backorder priority queues', 'points': 8, 'status': 'Not Started'}
                    ]
                },
                'C3.5': {
                    'name': 'Warehouse Management',
                    'user_stories': [
                        {'id': 'US-003.5.1', 'title': 'Configure integrated warehouse settings', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-003.5.2', 'title': 'Identify closest warehouse for fulfillment', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-003.5.3', 'title': 'Manage warehouse locations', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-003.5.4', 'title': 'Set warehouse operating hours', 'points': 5, 'status': 'Not Started'}
                    ]
                }
            }
        },
        'EPIC-004': {
            'name': 'Routing & Transportation Engine',
            'priority': 'P0',
            'phase': 3,
            'capabilities': {
                'C4.1': {
                    'name': 'MORO Integration',
                    'user_stories': [
                        {'id': 'US-004.1.1', 'title': 'Send order data to MORO routing engine', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-004.1.2', 'title': 'Receive multiple route options from MORO', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-004.1.3', 'title': 'Calculate routes using postal codes', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-004.1.4', 'title': 'Consider package dimensions and weight', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-004.1.5', 'title': 'TNT WebServices fallback when MORO unavailable', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-004.1.6', 'title': 'Manually override and select routes', 'points': 5, 'status': 'Not Started'}
                    ]
                },
                'C4.2': {
                    'name': 'Multi-modal Transportation',
                    'user_stories': [
                        {'id': 'US-004.2.1', 'title': 'Support air, ground, ocean modes', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-004.2.2', 'title': 'Configure mode selection rules', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-004.2.3', 'title': 'Calculate multi-leg routes', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-004.2.4', 'title': 'View cost/time for each mode', 'points': 5, 'status': 'Not Started'}
                    ]
                },
                'C4.3': {
                    'name': 'Next Flight Out Management',
                    'user_stories': [
                        {'id': 'US-004.3.1', 'title': 'Manage airline codes and services', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-004.3.2', 'title': 'Configure airports and containers', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-004.3.3', 'title': 'Update flight schedules via SSIM', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-004.3.4', 'title': 'Track flight updates via TFS', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-004.3.5', 'title': 'Set invalid flight ranges', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-004.3.6', 'title': 'Receive flight delay/cancellation alerts', 'points': 8, 'status': 'Not Started'}
                    ]
                },
                'C4.4': {
                    'name': 'Route Optimization',
                    'user_stories': [
                        {'id': 'US-004.4.1', 'title': 'Optimize routes for cost', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-004.4.2', 'title': 'Optimize routes for delivery time', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-004.4.3', 'title': 'Select fastest route for urgent orders', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-004.4.4', 'title': 'Apply customer routing profiles', 'points': 8, 'status': 'Not Started'}
                    ]
                },
                'C4.5': {
                    'name': 'Carrier Integration',
                    'user_stories': [
                        {'id': 'US-004.5.1', 'title': 'Integrate with UPS Quantum View', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-004.5.2', 'title': 'Integrate with FedEx via EasyPost', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-004.5.3', 'title': 'Direct TNT integration', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-004.5.4', 'title': 'Support Greyhound bus services', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-004.5.5', 'title': 'Rate shopping across carriers', 'points': 13, 'status': 'Not Started'}
                    ]
                }
            }
        },
        'EPIC-005': {
            'name': 'Vendor & Driver Management',
            'priority': 'P1',
            'phase': 3,
            'capabilities': {
                'C5.1': {
                    'name': 'Vendor Lifecycle Management',
                    'user_stories': [
                        {'id': 'US-005.1.1', 'title': 'Register vendors with document verification', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-005.1.2', 'title': 'Update vendor company and service areas', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-005.1.3', 'title': 'Manage vendor contracts', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-005.1.4', 'title': 'Track vendor performance metrics', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-005.1.5', 'title': 'Search vendors by type/location/skills', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-005.1.6', 'title': 'Activate/deactivate vendors', 'points': 5, 'status': 'Not Started'}
                    ]
                },
                'C5.2': {
                    'name': 'Driver Operations & Mobile App',
                    'user_stories': [
                        {'id': 'US-005.2.1', 'title': 'Receive job notifications on mobile', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-005.2.2', 'title': 'Accept/reject job assignments', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-005.2.3', 'title': 'View job details and route on mobile', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-005.2.4', 'title': 'Update milestones during delivery', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-005.2.5', 'title': 'Offline capability for mobile app', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-005.2.6', 'title': 'Track driver location in real-time', 'points': 13, 'status': 'Not Started'}
                    ]
                },
                'C5.3': {
                    'name': 'Job Assignment System',
                    'user_stories': [
                        {'id': 'US-005.3.1', 'title': 'View available drivers and status', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-005.3.2', 'title': 'Match driver skills to job requirements', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-005.3.3', 'title': 'Bulk assignment capabilities', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-005.3.4', 'title': 'Reassign jobs when needed', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-005.3.5', 'title': 'Auto-assign based on proximity and skills', 'points': 21, 'status': 'Not Started'}
                    ]
                },
                'C5.4': {
                    'name': 'Skills & Certification Management',
                    'user_stories': [
                        {'id': 'US-005.4.1', 'title': 'Add/remove skills to vendor profile', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-005.4.2', 'title': 'Track certification expiry dates', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-005.4.3', 'title': 'Skill-based job matching', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-005.4.4', 'title': 'Compliance reporting on certifications', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-005.4.5', 'title': 'Manage driver training records', 'points': 8, 'status': 'Not Started'}
                    ]
                },
                'C5.5': {
                    'name': 'POD & Milestone Updates',
                    'user_stories': [
                        {'id': 'US-005.5.1', 'title': 'Capture POD with signature', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-005.5.2', 'title': 'Capture POD with photo', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-005.5.3', 'title': 'Validate POD completeness', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-005.5.4', 'title': 'Send POD notifications to customer', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-005.5.5', 'title': 'Store POD documents for compliance', 'points': 8, 'status': 'Not Started'}
                    ]
                }
            }
        },
        'EPIC-006': {
            'name': 'Billing & Financial Management',
            'priority': 'P1',
            'phase': 4,
            'capabilities': {
                'C6.1': {
                    'name': 'Rate Schedule Management',
                    'user_stories': [
                        {'id': 'US-006.1.1', 'title': 'Create revenue rate schedules', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-006.1.2', 'title': 'Create cost rate schedules', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-006.1.3', 'title': 'Define rating attributes (mileage, weight)', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-006.1.4', 'title': 'Associate services to rate schedules', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-006.1.5', 'title': 'Effective date management for rates', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-006.1.6', 'title': 'Rate simulation tools', 'points': 13, 'status': 'Not Started'}
                    ]
                },
                'C6.2': {
                    'name': 'Billing Review & Resubmission',
                    'user_stories': [
                        {'id': 'US-006.2.1', 'title': 'Search orders by billing status', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-006.2.2', 'title': 'View vendor cost details', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-006.2.3', 'title': 'Compare quoted vs actual price', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-006.2.4', 'title': 'Edit and resubmit failed billing', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-006.2.5', 'title': 'Bulk resubmission via CSV', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-006.2.6', 'title': 'Exception reporting on billing failures', 'points': 8, 'status': 'Not Started'}
                    ]
                },
                'C6.3': {
                    'name': 'Storage Billing System',
                    'user_stories': [
                        {'id': 'US-006.3.1', 'title': 'Configure storage billing accounts', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-006.3.2', 'title': 'Set billing frequency (weekly/monthly)', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-006.3.3', 'title': 'Calculate storage charges by UOM', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-006.3.4', 'title': 'Generate storage invoices automatically', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-006.3.5', 'title': 'GBS integration for settlement', 'points': 13, 'status': 'Not Started'}
                    ]
                },
                'C6.4': {
                    'name': 'Accrual & Settlement Processing',
                    'user_stories': [
                        {'id': 'US-006.4.1', 'title': 'Run accrual extracts by date range', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-006.4.2', 'title': 'Generate cost accruals', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-006.4.3', 'title': 'Generate revenue accruals', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-006.4.4', 'title': 'Accrual history reports', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-006.4.5', 'title': 'Automated settlement processing', 'points': 21, 'status': 'Not Started'}
                    ]
                },
                'C6.5': {
                    'name': 'E2K Integration',
                    'user_stories': [
                        {'id': 'US-006.5.1', 'title': 'Send billing data to E2K', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-006.5.2', 'title': 'Receive invoice confirmations from E2K', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-006.5.3', 'title': 'Handle E2K charge code mapping', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-006.5.4', 'title': 'Configure E2K integration parameters', 'points': 5, 'status': 'Not Started'}
                    ]
                }
            }
        },
        'EPIC-007': {
            'name': 'Integration Platform',
            'priority': 'P0',
            'phase': 2,
            'capabilities': {
                'C7.1': {
                    'name': 'GIC/A2A Integration',
                    'user_stories': [
                        {'id': 'US-007.1.1', 'title': 'Receive customer XML from GIC', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-007.1.2', 'title': 'A2A validation and order transformation', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-007.1.3', 'title': 'Publish order events to A2A', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-007.1.4', 'title': 'Receive status updates from A2A', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-007.1.5', 'title': 'Maintain event audit trail in A2A', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-007.1.6', 'title': 'Retry mechanisms for failed messages', 'points': 13, 'status': 'Not Started'}
                    ]
                },
                'C7.2': {
                    'name': 'B2B Order Processing',
                    'user_stories': [
                        {'id': 'US-007.2.1', 'title': 'Process 90% orders via B2B channel', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-007.2.2', 'title': 'Support customer-specific XML formats', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-007.2.3', 'title': 'Validate B2B orders against rules', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-007.2.4', 'title': 'Queue B2B orders for processing', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-007.2.5', 'title': 'Send B2B acknowledgments', 'points': 8, 'status': 'Not Started'}
                    ]
                },
                'C7.3': {
                    'name': 'EDI Management',
                    'user_stories': [
                        {'id': 'US-007.3.1', 'title': 'Generate EDI notifications', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-007.3.2', 'title': 'Route EDI through A2A to GIC', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-007.3.3', 'title': 'Customer-specific EDI formats', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-007.3.4', 'title': 'Handle EDI delivery failures', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-007.3.5', 'title': 'EDI audit logs', 'points': 5, 'status': 'Not Started'}
                    ]
                },
                'C7.4': {
                    'name': 'WMS Integration',
                    'user_stories': [
                        {'id': 'US-007.4.1', 'title': 'Send fulfillment requests to WMS', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-007.4.2', 'title': 'Receive pick/pack/ship updates', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-007.4.3', 'title': 'Track warehouse operations', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-007.4.4', 'title': 'Handle WMS exceptions', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-007.4.5', 'title': 'Support multiple WMS instances', 'points': 13, 'status': 'Not Started'}
                    ]
                },
                'C7.5': {
                    'name': 'Print Services Integration',
                    'user_stories': [
                        {'id': 'US-007.5.1', 'title': 'CLIO integration for LPN labels', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-007.5.2', 'title': 'CLIO for commercial invoices', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-007.5.3', 'title': 'ConnectShip for shipping labels', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-007.5.4', 'title': 'ConnectShip for return labels', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-007.5.5', 'title': 'Batch printing capabilities', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-007.5.6', 'title': 'Reprint functionality', 'points': 5, 'status': 'Not Started'}
                    ]
                }
            }
        },
        'EPIC-008': {
            'name': 'Notification & Communication',
            'priority': 'P1',
            'phase': 4,
            'capabilities': {
                'C8.1': {
                    'name': 'Event-Driven Notifications',
                    'user_stories': [
                        {'id': 'US-008.1.1', 'title': 'Backorder notifications', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-008.1.2', 'title': 'Order confirmation notifications', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-008.1.3', 'title': 'Shipment tracking notifications', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-008.1.4', 'title': 'Delivery update notifications', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-008.1.5', 'title': 'Attempted delivery notifications', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-008.1.6', 'title': 'Flight delay/cancellation alerts', 'points': 8, 'status': 'Not Started'}
                    ]
                },
                'C8.2': {
                    'name': 'Multi-Channel Delivery',
                    'user_stories': [
                        {'id': 'US-008.2.1', 'title': 'Email notifications via SendGrid', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-008.2.2', 'title': 'SMS notifications via Twilio', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-008.2.3', 'title': 'Push notifications', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-008.2.4', 'title': 'In-app notifications', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-008.2.5', 'title': 'Manage channel preferences', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-008.2.6', 'title': 'Automated voice notifications', 'points': 13, 'status': 'Not Started'}
                    ]
                },
                'C8.3': {
                    'name': 'Subscription Management',
                    'user_stories': [
                        {'id': 'US-008.3.1', 'title': 'Subscribe to notification types', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-008.3.2', 'title': 'Unsubscribe from notifications', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-008.3.3', 'title': 'Manage subscription preferences', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-008.3.4', 'title': 'Configure notification templates', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-008.3.5', 'title': 'Track notification delivery status', 'points': 8, 'status': 'Not Started'}
                    ]
                }
            }
        },
        'EPIC-009': {
            'name': 'Service & Activity Configuration',
            'priority': 'P2',
            'phase': 5,
            'capabilities': {
                'C9.1': {
                    'name': 'Service Definition Management',
                    'user_stories': [
                        {'id': 'US-009.1.1', 'title': 'Create services with name/code/description', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-009.1.2', 'title': 'Define vendor types for services', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-009.1.3', 'title': 'Set service eligibility criteria', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-009.1.4', 'title': 'Configure service pricing', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-009.1.5', 'title': 'Enable/disable services', 'points': 5, 'status': 'Not Started'}
                    ]
                },
                'C9.2': {
                    'name': 'Activity Configuration',
                    'user_stories': [
                        {'id': 'US-009.2.1', 'title': 'Add activities to services', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-009.2.2', 'title': 'Set activity sequence and dependencies', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-009.2.3', 'title': 'Define activity attributes and charges', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-009.2.4', 'title': 'Track activity completion', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-009.2.5', 'title': 'Configure activity execution rules', 'points': 13, 'status': 'Not Started'}
                    ]
                },
                'C9.3': {
                    'name': 'Alarm Management',
                    'user_stories': [
                        {'id': 'US-009.3.1', 'title': 'Set yellow alarm offsets', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-009.3.2', 'title': 'Set red alarm offsets', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-009.3.3', 'title': 'Configure alarm types and notifications', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-009.3.4', 'title': 'Enable/disable alarms per activity', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-009.3.5', 'title': 'Alarm monitoring dashboard', 'points': 13, 'status': 'Not Started'}
                    ]
                }
            }
        },
        'EPIC-010': {
            'name': 'Geographic & Location Services',
            'priority': 'P2',
            'phase': 5,
            'capabilities': {
                'C10.1': {
                    'name': 'Geographic Configuration',
                    'user_stories': [
                        {'id': 'US-010.1.1', 'title': 'Configure landmasses and countries', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-010.1.2', 'title': 'Manage states and zip codes', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-010.1.3', 'title': 'Configure shared zones', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-010.1.4', 'title': 'Set operating hours by location', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-010.1.5', 'title': 'Maintain geographic hierarchies', 'points': 13, 'status': 'Not Started'}
                    ]
                },
                'C10.2': {
                    'name': 'PUDO Location Management',
                    'user_stories': [
                        {'id': 'US-010.2.1', 'title': 'Create pickup/dropoff locations', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-010.2.2', 'title': 'Search PUDO locations by code/city', 'points': 5, 'status': 'Not Started'},
                        {'id': 'US-010.2.3', 'title': 'Validate PUDO location availability', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-010.2.4', 'title': 'Manage PUDO operating hours', 'points': 5, 'status': 'Not Started'}
                    ]
                }
            }
        },
        'EPIC-011': {
            'name': 'Platform Infrastructure & Security',
            'priority': 'P0',
            'phase': 0,
            'capabilities': {
                'C11.1': {
                    'name': 'Cloud Infrastructure Setup',
                    'user_stories': [
                        {'id': 'US-011.1.1', 'title': 'Provision Azure resource groups', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-011.1.2', 'title': 'Setup Hub-Spoke virtual networks', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-011.1.3', 'title': 'Configure Azure Firewall and NSGs', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-011.1.4', 'title': 'Setup AKS cluster with auto-scaling', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-011.1.5', 'title': 'Install Istio service mesh', 'points': 13, 'status': 'Not Started'}
                    ]
                },
                'C11.2': {
                    'name': 'Security Implementation',
                    'user_stories': [
                        {'id': 'US-011.2.1', 'title': 'Configure Azure AD B2C authentication', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-011.2.2', 'title': 'Setup Azure Key Vault for secrets', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-011.2.3', 'title': 'Implement RBAC and policies', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-011.2.4', 'title': 'Configure managed identities', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-011.2.5', 'title': 'Setup secret rotation', 'points': 8, 'status': 'Not Started'}
                    ]
                },
                'C11.3': {
                    'name': 'DevOps Automation',
                    'user_stories': [
                        {'id': 'US-011.3.1', 'title': 'Create CI/CD pipelines in Azure DevOps', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-011.3.2', 'title': 'Implement blue-green deployment', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-011.3.3', 'title': 'Configure automated testing', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-011.3.4', 'title': 'Setup monitoring with App Insights', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-011.3.5', 'title': 'Implement distributed tracing', 'points': 8, 'status': 'Not Started'}
                    ]
                }
            }
        },
        'EPIC-012': {
            'name': 'Reporting & Analytics',
            'priority': 'P2',
            'phase': 5,
            'capabilities': {
                'C12.1': {
                    'name': 'Operational Reports',
                    'user_stories': [
                        {'id': 'US-012.1.1', 'title': 'Order volume and trend reports', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-012.1.2', 'title': 'Performance metrics dashboard', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-012.1.3', 'title': 'SLA compliance reports', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-012.1.4', 'title': 'Exception and error reports', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-012.1.5', 'title': 'Inventory turnover analysis', 'points': 8, 'status': 'Not Started'}
                    ]
                },
                'C12.2': {
                    'name': 'Financial Analytics',
                    'user_stories': [
                        {'id': 'US-012.2.1', 'title': 'Revenue and cost analysis', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-012.2.2', 'title': 'Billing reconciliation reports', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-012.2.3', 'title': 'Profitability by customer/route', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-012.2.4', 'title': 'Accrual vs actual variance', 'points': 8, 'status': 'Not Started'},
                        {'id': 'US-012.2.5', 'title': 'Storage billing analytics', 'points': 8, 'status': 'Not Started'}
                    ]
                }
            }
        },
        'EPIC-NFR': {
            'name': 'Non-Functional Requirements',
            'priority': 'P0',
            'phase': 6,
            'capabilities': {
                'CNFR.1': {
                    'name': 'Performance Optimization',
                    'user_stories': [
                        {'id': 'US-NFR.1.1', 'title': 'API response time < 200ms (P95)', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-NFR.1.2', 'title': 'Support 10,000 orders/hour', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-NFR.1.3', 'title': 'Handle 1000+ concurrent users', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-NFR.1.4', 'title': 'Page load time < 2 seconds', 'points': 13, 'status': 'Not Started'}
                    ]
                },
                'CNFR.2': {
                    'name': 'Security & Compliance',
                    'user_stories': [
                        {'id': 'US-NFR.2.1', 'title': 'PCI DSS compliance', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-NFR.2.2', 'title': 'SOC 2 Type II certification', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-NFR.2.3', 'title': 'GDPR compliance for EU', 'points': 13, 'status': 'Not Started'},
                        {'id': 'US-NFR.2.4', 'title': 'OWASP Top 10 protection', 'points': 13, 'status': 'Not Started'}
                    ]
                },
                'CNFR.3': {
                    'name': 'Reliability & Availability',
                    'user_stories': [
                        {'id': 'US-NFR.3.1', 'title': '99.95% uptime SLA', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-NFR.3.2', 'title': 'RTO: 1 hour, RPO: 15 minutes', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-NFR.3.3', 'title': 'Multi-region deployment', 'points': 21, 'status': 'Not Started'},
                        {'id': 'US-NFR.3.4', 'title': 'Automatic failover', 'points': 13, 'status': 'Not Started'}
                    ]
                }
            }
        }
    }

# Initialize session state
if 'epics_data' not in st.session_state:
    st.session_state.epics_data = initialize_epics_data()

# Resource rates configuration
RESOURCE_RATES = {
    'onsite': {
        'Head of Technology': 140,
        'Senior Technical Architect': 113,
        'Technical Architect': 103,
        'Project Manager': 103,
        'Senior Developer': 87,
        'Team Lead': 89,
        'DevOps Engineer': 87,
        'Business Analyst': 82,
        'Integration Specialist': 89
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

# Phase configuration
PHASES = {
    0: {'name': 'Foundation & Architecture', 'duration': 2, 'onsite': 2, 'offshore': 3},
    1: {'name': 'Core Platform & Customer', 'duration': 3, 'onsite': 4, 'offshore': 7},
    2: {'name': 'Order & Inventory', 'duration': 3, 'onsite': 5, 'offshore': 13},
    3: {'name': 'Routing & Transportation', 'duration': 3, 'onsite': 6, 'offshore': 13},
    4: {'name': 'Billing & Financial', 'duration': 3, 'onsite': 6, 'offshore': 13},
    5: {'name': 'Advanced Features', 'duration': 2, 'onsite': 4, 'offshore': 10},
    6: {'name': 'Testing & Migration', 'duration': 2, 'onsite': 4, 'offshore': 12}
}

def calculate_comprehensive_metrics():
    """Calculate comprehensive metrics for all EPICs and stories"""
    total_stories = 0
    total_points = 0
    epic_metrics = {}
    capability_metrics = {}
    
    for epic_id, epic_data in st.session_state.epics_data.items():
        epic_stories = 0
        epic_points = 0
        
        for cap_id, cap_data in epic_data['capabilities'].items():
            cap_stories = len(cap_data['user_stories'])
            cap_points = sum(story['points'] for story in cap_data['user_stories'])
            
            epic_stories += cap_stories
            epic_points += cap_points
            
            capability_metrics[f"{epic_id}-{cap_id}"] = {
                'name': cap_data['name'],
                'stories': cap_stories,
                'points': cap_points
            }
        
        total_stories += epic_stories
        total_points += epic_points
        
        epic_metrics[epic_id] = {
            'name': epic_data['name'],
            'stories': epic_stories,
            'points': epic_points,
            'priority': epic_data['priority'],
            'phase': epic_data['phase']
        }
    
    return total_stories, total_points, epic_metrics, capability_metrics

def calculate_phase_metrics():
    """Calculate metrics by phase"""
    phase_metrics = {i: {'stories': 0, 'points': 0, 'epics': []} for i in range(7)}
    
    for epic_id, epic_data in st.session_state.epics_data.items():
        phase = epic_data['phase']
        phase_metrics[phase]['epics'].append(epic_id)
        
        for cap_data in epic_data['capabilities'].values():
            phase_metrics[phase]['stories'] += len(cap_data['user_stories'])
            phase_metrics[phase]['points'] += sum(story['points'] for story in cap_data['user_stories'])
    
    return phase_metrics

def main():
    st.title("🚀 SPLUS RTM Platform Modernization Dashboard")
    st.markdown("### Complete Interactive Program Management System")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select View",
        ["Executive Dashboard", "EPICs & User Stories", "Timeline & Phases", 
         "Cost Analysis", "Resource Planning", "Reports", "Sprint Planning"]
    )
    
    if page == "Executive Dashboard":
        show_executive_dashboard()
    elif page == "EPICs & User Stories":
        show_epics_user_stories()
    elif page == "Timeline & Phases":
        show_timeline_phases()
    elif page == "Cost Analysis":
        show_cost_analysis()
    elif page == "Resource Planning":
        show_resource_planning()
    elif page == "Reports":
        show_reports()
    elif page == "Sprint Planning":
        show_sprint_planning()

def show_executive_dashboard():
    """Display executive dashboard with comprehensive metrics"""
    st.header("📊 Executive Dashboard")
    
    # Calculate comprehensive metrics
    total_stories, total_points, epic_metrics, _ = calculate_comprehensive_metrics()
    phase_metrics = calculate_phase_metrics()
    
    # Key metrics row
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("Total EPICs", len(st.session_state.epics_data))
    with col2:
        st.metric("Total Capabilities", sum(len(e['capabilities']) for e in st.session_state.epics_data.values()))
    with col3:
        st.metric("User Stories", total_stories)
    with col4:
        st.metric("Story Points", f"{total_points:,}")
    with col5:
        st.metric("Avg Points/Story", f"{total_points/total_stories:.1f}")
    with col6:
        st.metric("Duration", "18 Months")
    
    # Visualizations
    col1, col2 = st.columns(2)
    
    with col1:
        # Epic points distribution
        epic_names = [epic_metrics[eid]['name'][:20] + '...' for eid in epic_metrics]
        epic_points = [epic_metrics[eid]['points'] for eid in epic_metrics]
        
        fig = go.Figure(data=[
            go.Bar(x=epic_names, y=epic_points, marker_color='lightblue',
                  text=epic_points, textposition='auto')
        ])
        fig.update_layout(
            title="Story Points by EPIC",
            xaxis_title="EPIC",
            yaxis_title="Story Points",
            height=400,
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Phase distribution
        phase_names = [PHASES[i]['name'] for i in range(7)]
        phase_points = [phase_metrics[i]['points'] for i in range(7)]
        
        fig = go.Figure(data=[
            go.Bar(x=phase_names, y=phase_points, marker_color='lightgreen',
                  text=phase_points, textposition='auto')
        ])
        fig.update_layout(
            title="Story Points by Phase",
            xaxis_title="Phase",
            yaxis_title="Story Points",
            height=400,
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Priority distribution
    st.subheader("Priority Distribution")
    priority_counts = {'P0': 0, 'P1': 0, 'P2': 0}
    priority_points = {'P0': 0, 'P1': 0, 'P2': 0}
    
    for epic_id, metrics in epic_metrics.items():
        priority = metrics['priority']
        priority_counts[priority] += 1
        priority_points[priority] += metrics['points']
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = go.Figure(data=[go.Pie(labels=list(priority_counts.keys()), 
                                     values=list(priority_counts.values()),
                                     title="EPICs by Priority")])
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = go.Figure(data=[go.Pie(labels=list(priority_points.keys()), 
                                     values=list(priority_points.values()),
                                     title="Story Points by Priority")])
        st.plotly_chart(fig, use_container_width=True)

def show_epics_user_stories():
    """Display and manage EPICs with all user stories"""
    st.header("📋 EPICs & User Stories Management")
    
    # Summary statistics
    total_stories, total_points, epic_metrics, capability_metrics = calculate_comprehensive_metrics()
    
    st.info(f"**Total:** {len(st.session_state.epics_data)} EPICs | "
            f"{len(capability_metrics)} Capabilities | "
            f"{total_stories} User Stories | "
            f"{total_points:,} Story Points")
    
    # Filter options
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_phase = st.selectbox("Filter by Phase", 
                                   ["All"] + [f"Phase {i}" for i in range(7)])
    with col2:
        filter_priority = st.selectbox("Filter by Priority", 
                                      ["All", "P0", "P1", "P2"])
    with col3:
        search_term = st.text_input("Search EPICs/Stories", "")
    
    # Display EPICs
    for epic_id, epic_data in st.session_state.epics_data.items():
        # Apply filters
        if filter_phase != "All" and epic_data['phase'] != int(filter_phase.split()[1]):
            continue
        if filter_priority != "All" and epic_data['priority'] != filter_priority:
            continue
        if search_term and search_term.lower() not in epic_data['name'].lower():
            continue
        
        epic_metrics_data = epic_metrics.get(epic_id, {})
        
        with st.expander(
            f"{epic_id}: {epic_data['name']} "
            f"({epic_data['priority']}, Phase {epic_data['phase']}) - "
            f"{epic_metrics_data.get('stories', 0)} stories, "
            f"{epic_metrics_data.get('points', 0)} points"
        ):
            # EPIC details tabs
            tab1, tab2, tab3 = st.tabs(["Overview", "User Stories", "Edit EPIC"])
            
            with tab1:
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Priority", epic_data['priority'])
                with col2:
                    st.metric("Phase", epic_data['phase'])
                with col3:
                    st.metric("Capabilities", len(epic_data['capabilities']))
                with col4:
                    st.metric("Total Points", epic_metrics_data.get('points', 0))
            
            with tab2:
                # Display capabilities and user stories
                for cap_id, cap_data in epic_data['capabilities'].items():
                    st.markdown(f"**{cap_id}: {cap_data['name']}**")
                    
                    # Create DataFrame for user stories
                    if cap_data['user_stories']:
                        df_stories = pd.DataFrame(cap_data['user_stories'])
                        df_stories = df_stories[['id', 'title', 'points', 'status']]
                        
                        # Display as editable dataframe
                        edited_df = st.data_editor(
                            df_stories,
                            column_config={
                                "status": st.column_config.SelectboxColumn(
                                    "Status",
                                    options=["Not Started", "In Progress", "Completed"],
                                    default="Not Started"
                                )
                            },
                            hide_index=True,
                            key=f"stories_{epic_id}_{cap_id}"
                        )
                        
                        # Update stories if edited
                        cap_data['user_stories'] = edited_df.to_dict('records')
                        
                        # Capability summary
                        cap_points = sum(story['points'] for story in cap_data['user_stories'])
                        st.caption(f"Total: {len(cap_data['user_stories'])} stories, {cap_points} points")
                    
                    st.markdown("---")
            
            with tab3:
                # Edit EPIC details
                col1, col2, col3 = st.columns(3)
                with col1:
                    epic_data['name'] = st.text_input(f"Name_{epic_id}", 
                                                      epic_data['name'])
                with col2:
                    epic_data['priority'] = st.selectbox(f"Priority_{epic_id}",
                                                        ["P0", "P1", "P2"],
                                                        index=["P0", "P1", "P2"].index(epic_data['priority']))
                with col3:
                    epic_data['phase'] = st.selectbox(f"Phase_{epic_id}",
                                                     list(range(7)),
                                                     index=epic_data['phase'])
                
                if st.button(f"Save Changes for {epic_id}"):
                    st.success("Changes saved!")
                    st.rerun()

def show_timeline_phases():
    """Display timeline and phase information"""
    st.header("📅 Timeline & Phases")
    
    phase_metrics = calculate_phase_metrics()
    
    # Create Gantt chart
    gantt_data = []
    start_date = datetime(2024, 1, 1)
    
    for phase_id, phase_info in PHASES.items():
        end_date = start_date + timedelta(days=phase_info['duration'] * 30)
        gantt_data.append({
            'Phase': f"Phase {phase_id}: {phase_info['name']}",
            'Start': start_date,
            'End': end_date,
            'Stories': phase_metrics[phase_id]['stories'],
            'Points': phase_metrics[phase_id]['points']
        })
        start_date = end_date
    
    df_gantt = pd.DataFrame(gantt_data)
    
    # Gantt chart
    fig = px.timeline(
        df_gantt,
        x_start="Start",
        x_end="End",
        y="Phase",
        title="Project Timeline - 18 Month Program",
        hover_data=['Stories', 'Points']
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)
    
    # Phase details
    st.subheader("Phase Deliverables")
    
    for phase_id, phase_info in PHASES.items():
        metrics = phase_metrics[phase_id]
        
        with st.expander(
            f"Phase {phase_id}: {phase_info['name']} - "
            f"{metrics['stories']} stories, {metrics['points']} points"
        ):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Duration", f"{phase_info['duration']} months")
            with col2:
                st.metric("User Stories", metrics['stories'])
            with col3:
                st.metric("Story Points", metrics['points'])
            with col4:
                st.metric("EPICs", len(metrics['epics']))
            
            # List EPICs in this phase
            st.markdown("**EPICs in this phase:**")
            for epic_id in metrics['epics']:
                epic_name = st.session_state.epics_data[epic_id]['name']
                st.write(f"- {epic_id}: {epic_name}")

def show_cost_analysis():
    """Show comprehensive cost analysis"""
    st.header("💰 Cost Analysis")
    
    # Phase cost calculation
    phase_costs = {}
    for phase_id, phase_info in PHASES.items():
        onsite_cost = phase_info['onsite'] * 113 * 160 * phase_info['duration']
        offshore_cost = phase_info['offshore'] * 22 * 160 * phase_info['duration']
        phase_costs[phase_id] = {
            'onsite': onsite_cost,
            'offshore': offshore_cost,
            'total': onsite_cost + offshore_cost
        }
    
    # Display cost breakdown
    st.subheader("Phase-wise Cost Breakdown")
    
    cost_data = []
    for phase_id, phase_info in PHASES.items():
        cost_data.append({
            'Phase': f"Phase {phase_id}",
            'Name': phase_info['name'],
            'Duration': f"{phase_info['duration']} months",
            'Onsite Cost': f"${phase_costs[phase_id]['onsite']:,.0f}",
            'Offshore Cost': f"${phase_costs[phase_id]['offshore']:,.0f}",
            'Total Cost': f"${phase_costs[phase_id]['total']:,.0f}"
        })
    
    df_costs = pd.DataFrame(cost_data)
    st.dataframe(df_costs, use_container_width=True)
    
    # Total program cost
    total_dev_cost = sum(pc['total'] for pc in phase_costs.values())
    infrastructure = 500000
    contingency = (total_dev_cost + infrastructure) * 0.15
    grand_total = total_dev_cost + infrastructure + contingency
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Development Cost", f"${total_dev_cost:,.0f}")
    with col2:
        st.metric("Infrastructure", f"${infrastructure:,.0f}")
    with col3:
        st.metric("Contingency (15%)", f"${contingency:,.0f}")
    with col4:
        st.metric("Grand Total", f"${grand_total:,.0f}")
    
    # Cost visualizations
    col1, col2 = st.columns(2)
    
    with col1:
        # Cost by phase pie chart
        labels = [f"Phase {i}" for i in range(7)]
        values = [phase_costs[i]['total'] for i in range(7)]
        
        fig = go.Figure(data=[go.Pie(labels=labels, values=values)])
        fig.update_layout(title="Cost Distribution by Phase")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Onsite vs Offshore
        phases = [f"P{i}" for i in range(7)]
        onsite = [phase_costs[i]['onsite'] for i in range(7)]
        offshore = [phase_costs[i]['offshore'] for i in range(7)]
        
        fig = go.Figure(data=[
            go.Bar(name='Onsite', x=phases, y=onsite),
            go.Bar(name='Offshore', x=phases, y=offshore)
        ])
        fig.update_layout(
            barmode='stack',
            title="Onsite vs Offshore Cost Distribution"
        )
        st.plotly_chart(fig, use_container_width=True)

def show_resource_planning():
    """Show resource planning"""
    st.header("👥 Resource Planning")
    
    # Select phase
    selected_phase = st.selectbox(
        "Select Phase",
        [f"Phase {i}: {PHASES[i]['name']}" for i in range(7)]
    )
    phase_id = int(selected_phase.split(":")[0].split()[1])
    
    st.subheader(f"Resource Allocation for {selected_phase}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Onsite Team Configuration**")
        for role, rate in RESOURCE_RATES['onsite'].items():
            count = st.number_input(f"{role} ({rate}/hr)", 
                                   min_value=0, max_value=5, value=1,
                                   key=f"onsite_{role}_{phase_id}")
    
    with col2:
        st.markdown("**Offshore Team Configuration**")
        for role, rate in RESOURCE_RATES['offshore'].items():
            count = st.number_input(f"{role} ({rate}/hr)",
                                   min_value=0, max_value=10, value=2,
                                   key=f"offshore_{role}_{phase_id}")

def show_reports():
    """Generate various reports"""
    st.header("📊 Reports Generation")
    
    report_type = st.selectbox(
        "Select Report Type",
        ["Executive Summary", "User Stories Report", "Sprint Report", "Velocity Report"]
    )
    
    if report_type == "Executive Summary":
        generate_executive_report()
    elif report_type == "User Stories Report":
        generate_user_stories_report()
    elif report_type == "Sprint Report":
        generate_sprint_report()
    elif report_type == "Velocity Report":
        generate_velocity_report()

def generate_executive_report():
    """Generate executive summary report"""
    st.subheader("Executive Summary Report")
    
    total_stories, total_points, epic_metrics, _ = calculate_comprehensive_metrics()
    
    report_text = f"""
    # SPLUS RTM MODERNIZATION - EXECUTIVE SUMMARY
    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
    
    ## Program Overview
    - Total EPICs: {len(st.session_state.epics_data)}
    - Total User Stories: {total_stories}
    - Total Story Points: {total_points:,}
    - Average Points per Story: {total_points/total_stories:.1f}
    - Duration: 18 Months
    
    ## EPIC Summary
    """
    
    for epic_id, metrics in epic_metrics.items():
        report_text += f"""
    {epic_id}: {metrics['name']}
    - Priority: {metrics['priority']}
    - Phase: {metrics['phase']}
    - Stories: {metrics['stories']}
    - Points: {metrics['points']}
    """
    
    st.text_area("Report Preview", report_text, height=400)
    
    st.download_button(
        label="Download Report",
        data=report_text,
        file_name=f"RTM_Executive_Summary_{datetime.now().strftime('%Y%m%d')}.txt",
        mime="text/plain"
    )

def generate_user_stories_report():
    """Generate comprehensive user stories report"""
    st.subheader("User Stories Report")
    
    stories_list = []
    for epic_id, epic_data in st.session_state.epics_data.items():
        for cap_id, cap_data in epic_data['capabilities'].items():
            for story in cap_data['user_stories']:
                stories_list.append({
                    'EPIC ID': epic_id,
                    'EPIC Name': epic_data['name'],
                    'Capability ID': cap_id,
                    'Capability': cap_data['name'],
                    'Story ID': story['id'],
                    'Story Title': story['title'],
                    'Points': story['points'],
                    'Status': story.get('status', 'Not Started')
                })
    
    df_stories = pd.DataFrame(stories_list)
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Stories", len(df_stories))
    with col2:
        st.metric("Total Points", df_stories['Points'].sum())
    with col3:
        st.metric("Average Points", f"{df_stories['Points'].mean():.1f}")
    
    st.dataframe(df_stories, use_container_width=True)
    
    # Download CSV
    csv = df_stories.to_csv(index=False)
    st.download_button(
        label="Download User Stories CSV",
        data=csv,
        file_name=f"RTM_User_Stories_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

def generate_sprint_report():
    """Generate sprint planning report"""
    st.subheader("Sprint Planning Report")
    
    sprint_duration = st.number_input("Sprint Duration (weeks)", min_value=1, max_value=4, value=2)
    velocity = st.number_input("Team Velocity (points/sprint)", min_value=10, max_value=100, value=40)
    
    total_stories, total_points, _, _ = calculate_comprehensive_metrics()
    total_sprints = int(np.ceil(total_points / velocity))
    
    st.info(f"Based on velocity of {velocity} points per {sprint_duration}-week sprint, "
            f"the project will require approximately {total_sprints} sprints "
            f"({total_sprints * sprint_duration} weeks)")

def generate_velocity_report():
    """Generate velocity analysis"""
    st.subheader("Velocity Analysis")
    
    phase_metrics = calculate_phase_metrics()
    
    # Create velocity chart
    phases = [f"Phase {i}" for i in range(7)]
    points = [phase_metrics[i]['points'] for i in range(7)]
    durations = [PHASES[i]['duration'] for i in range(7)]
    velocities = [p/d if d > 0 else 0 for p, d in zip(points, durations)]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Points', x=phases, y=points))
    fig.add_trace(go.Scatter(name='Velocity', x=phases, y=velocities, 
                            yaxis='y2', mode='lines+markers'))
    
    fig.update_layout(
        title='Phase Points and Velocity',
        yaxis=dict(title='Story Points'),
        yaxis2=dict(title='Velocity (points/month)', overlaying='y', side='right'),
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

def show_sprint_planning():
    """Sprint planning interface"""
    st.header("🏃 Sprint Planning")
    
    # Sprint configuration
    col1, col2, col3 = st.columns(3)
    with col1:
        sprint_number = st.number_input("Sprint Number", min_value=1, value=1)
    with col2:
        sprint_capacity = st.number_input("Sprint Capacity (points)", 
                                         min_value=10, max_value=100, value=40)
    with col3:
        team_size = st.number_input("Team Size", min_value=3, max_value=15, value=8)
    
    st.subheader(f"Sprint {sprint_number} Planning")
    
    # Available stories for sprint
    st.markdown("### Available User Stories")
    
    available_stories = []
    for epic_id, epic_data in st.session_state.epics_data.items():
        for cap_id, cap_data in epic_data['capabilities'].items():
            for story in cap_data['user_stories']:
                if story.get('status', 'Not Started') == 'Not Started':
                    available_stories.append({
                        'Select': False,
                        'Story ID': story['id'],
                        'Title': story['title'][:50] + '...',
                        'Points': story['points'],
                        'EPIC': epic_id,
                        'Priority': epic_data['priority']
                    })
    
    if available_stories:
        df_available = pd.DataFrame(available_stories)
        
        # Sort by priority and points
        priority_order = {'P0': 0, 'P1': 1, 'P2': 2}
        df_available['Priority_Order'] = df_available['Priority'].map(priority_order)
        df_available = df_available.sort_values(['Priority_Order', 'Points'])
        df_available = df_available.drop('Priority_Order', axis=1)
        
        # Display selectable dataframe
        selected_df = st.data_editor(
            df_available,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select")
            },
            hide_index=True,
            key="sprint_selection"
        )
        
        # Calculate selected points
        selected_stories = selected_df[selected_df['Select'] == True]
        selected_points = selected_stories['Points'].sum()
        
        # Display sprint summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Selected Stories", len(selected_stories))
        with col2:
            st.metric("Selected Points", selected_points)
        with col3:
            utilization = (selected_points / sprint_capacity * 100) if sprint_capacity > 0 else 0
            st.metric("Capacity Utilization", f"{utilization:.0f}%")
        
        if selected_points > sprint_capacity:
            st.warning(f"Selected points ({selected_points}) exceed sprint capacity ({sprint_capacity})")
        
        if st.button("Commit Sprint"):
            st.success(f"Sprint {sprint_number} committed with {len(selected_stories)} stories!")

if __name__ == "__main__":
    main()