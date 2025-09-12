"""
UPS MCP Vulnerability Demonstration - Enhanced Version
Streamlit Application with Step-by-Step Attack Visualization
Based on https://github.com/UPS-API/ups-mcp
"""

import streamlit as st
import json
import os
import hashlib
import requests
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, Any, List, Optional
import time
import base64
from dataclasses import dataclass
import plotly.graph_objects as go
import plotly.express as px
import random
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Page configuration
st.set_page_config(
    page_title="UPS MCP Security Analysis",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .vulnerability-box {
        background-color: #fee;
        border-left: 5px solid #e74c3c;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .secure-box {
        background-color: #e8f8f5;
        border-left: 5px solid #27ae60;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .attack-box {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .code-exploit {
        background-color: #2b2b2b;
        color: #f8f8f2;
        padding: 10px;
        border-radius: 5px;
        font-family: 'Courier New', monospace;
        margin: 10px 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    .step-indicator {
        display: flex;
        align-items: center;
        margin: 20px 0;
    }
    .step-circle {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        margin-right: 10px;
    }
    .step-active {
        background: #27ae60;
        color: white;
    }
    .step-pending {
        background: #95a5a6;
        color: white;
    }
    .step-complete {
        background: #2ecc71;
        color: white;
    }
    .data-theft-container {
        background: #1a1a1a;
        color: #00ff00;
        font-family: 'Courier New', monospace;
        padding: 20px;
        border-radius: 10px;
        max-height: 400px;
        overflow-y: auto;
    }
    .stolen-data-row {
        margin: 5px 0;
        padding: 5px;
        border-left: 3px solid #00ff00;
        animation: fadeIn 0.5s;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateX(-20px); }
        to { opacity: 1; transform: translateX(0); }
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# MOCK DATA GENERATOR
# ============================================================================

class MockDataGenerator:
    """Generates realistic looking tracking data for demonstration"""
    
    @staticmethod
    def generate_tracking_numbers(count: int = 100) -> List[str]:
        """Generate realistic UPS tracking numbers"""
        tracking_numbers = []
        prefixes = ["1Z", "T", "K", ""]
        
        for i in range(count):
            if i < 70:  # 70% standard format
                prefix = "1Z"
                middle = ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=6))
                suffix = ''.join(random.choices("0123456789", k=10))
                tracking = f"{prefix}{middle}{suffix}"
            else:  # 30% other formats
                prefix = random.choice(prefixes[1:])
                number = ''.join(random.choices("0123456789", k=random.randint(10, 18)))
                tracking = f"{prefix}{number}"
            
            tracking_numbers.append(tracking)
        
        return tracking_numbers
    
    @staticmethod
    def generate_customer_data(tracking_number: str) -> Dict[str, Any]:
        """Generate realistic customer data for a tracking number"""
        
        first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "Robert", "Lisa", "James", "Mary"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        streets = ["Main St", "Oak Ave", "Elm St", "Park Rd", "First Ave", "Second St", "Maple Dr", "Cedar Ln", "Washington Blvd", "Spring St"]
        cities = ["Atlanta", "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas"]
        states = ["GA", "NY", "CA", "IL", "TX", "AZ", "PA", "TX", "CA", "TX"]
        
        # Generate consistent data based on tracking number hash
        hash_val = hash(tracking_number)
        random.seed(hash_val)
        
        customer_data = {
            "tracking_number": tracking_number,
            "shipper": {
                "name": f"{random.choice(first_names)} {random.choice(last_names)}",
                "company": f"{random.choice(['ABC', 'XYZ', 'Global', 'Premier', 'Elite'])} {random.choice(['Corp', 'Inc', 'LLC', 'Industries'])}",
                "address": f"{random.randint(100, 9999)} {random.choice(streets)}",
                "city": random.choice(cities),
                "state": random.choice(states),
                "zip": f"{random.randint(10000, 99999)}",
                "phone": f"+1-{random.randint(200, 999)}-{random.randint(200, 999)}-{random.randint(1000, 9999)}"
            },
            "recipient": {
                "name": f"{random.choice(first_names)} {random.choice(last_names)}",
                "address": f"{random.randint(100, 9999)} {random.choice(streets)}",
                "city": random.choice(cities),
                "state": random.choice(states),
                "zip": f"{random.randint(10000, 99999)}",
                "phone": f"+1-{random.randint(200, 999)}-{random.randint(200, 999)}-{random.randint(1000, 9999)}",
                "email": f"{random.choice(first_names).lower()}.{random.choice(last_names).lower()}@{random.choice(['gmail', 'yahoo', 'outlook'])}.com"
            },
            "package_details": {
                "weight": f"{random.randint(1, 50)} lbs",
                "dimensions": f"{random.randint(10, 30)}x{random.randint(10, 30)}x{random.randint(10, 30)} in",
                "value": f"${random.randint(50, 5000)}.00",
                "description": random.choice(["Electronics", "Clothing", "Documents", "Medical Supplies", "Auto Parts", "Books", "Food Items"]),
                "service_type": random.choice(["Next Day Air", "2nd Day Air", "Ground", "3 Day Select", "Next Day Air Saver"])
            },
            "status": {
                "current": random.choice(["Delivered", "In Transit", "Out for Delivery", "Processing", "Picked Up"]),
                "location": f"{random.choice(cities)}, {random.choice(states)}",
                "timestamp": (datetime.now() - timedelta(hours=random.randint(1, 72))).strftime("%Y-%m-%d %H:%M:%S")
            },
            "estimated_delivery": (datetime.now() + timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%d"),
            "actual_delivery": None if random.random() > 0.5 else (datetime.now() - timedelta(days=random.randint(0, 3))).strftime("%Y-%m-%d"),
            "signature": random.choice([None, "J. Smith", "M. Johnson", "Package left at door", "Signed by: Receptionist"])
        }
        
        random.seed()  # Reset random seed
        return customer_data

# ============================================================================
# STEP-BY-STEP ATTACK EXECUTOR
# ============================================================================

class StepByStepAttackExecutor:
    """Executes attacks with visual step-by-step progression"""
    
    def __init__(self):
        self.current_step = 0
        self.steps_completed = []
        self.stolen_data = []
        self.api_calls_made = 0
        self.start_time = None
        
    def show_attack_steps(self):
        """Display step-by-step attack execution"""
        st.header("🎯 Step-by-Step Attack Execution")
        
        # Attack steps definition
        attack_steps = [
            {
                "id": 1,
                "name": "Environment Reconnaissance",
                "description": "Scanning for exposed environment variables",
                "duration": 2
            },
            {
                "id": 2,
                "name": "Credential Extraction",
                "description": "Extracting OAuth CLIENT_ID and CLIENT_SECRET",
                "duration": 3
            },
            {
                "id": 3,
                "name": "API Endpoint Discovery",
                "description": "Identifying available UPS API endpoints",
                "duration": 2
            },
            {
                "id": 4,
                "name": "Rate Limit Testing",
                "description": "Checking for rate limiting (spoiler: none exists)",
                "duration": 2
            },
            {
                "id": 5,
                "name": "Data Exfiltration",
                "description": "Extracting tracking numbers and customer data",
                "duration": 5
            }
        ]
        
        # Progress indicator
        progress_cols = st.columns(len(attack_steps))
        for idx, (col, step) in enumerate(zip(progress_cols, attack_steps)):
            with col:
                if idx < len(self.steps_completed):
                    st.markdown(f"""
                    <div style="text-align: center;">
                        <div class="step-circle step-complete">✓</div>
                        <small>{step['name']}</small>
                    </div>
                    """, unsafe_allow_html=True)
                elif idx == self.current_step:
                    st.markdown(f"""
                    <div style="text-align: center;">
                        <div class="step-circle step-active">{step['id']}</div>
                        <small><b>{step['name']}</b></small>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="text-align: center;">
                        <div class="step-circle step-pending">{step['id']}</div>
                        <small>{step['name']}</small>
                    </div>
                    """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Control buttons
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            if st.button("🚀 Execute Attack Chain", type="primary", use_container_width=True):
                self.execute_attack_chain(attack_steps)
        
        # Display current attack status
        if 'attack_status' in st.session_state:
            status = st.session_state['attack_status']
            
            if status['active']:
                st.markdown(f"""
                <div class="attack-box">
                <h4>⚡ Attack in Progress</h4>
                <p><b>Current Step:</b> {status['current_step']}</p>
                <p><b>Action:</b> {status['action']}</p>
                </div>
                """, unsafe_allow_html=True)
            
            # Show extracted credentials if found
            if 'extracted_credentials' in st.session_state:
                creds = st.session_state['extracted_credentials']
                st.markdown("""
                <div class="vulnerability-box">
                <h4>🔓 Extracted Credentials</h4>
                </div>
                """, unsafe_allow_html=True)
                
                st.code(f"""
CLIENT_ID = {creds['client_id']}
CLIENT_SECRET = {creds['client_secret']}
ENVIRONMENT = {creds['environment']}
API_ENDPOINT = {creds['endpoint']}
                """)
            
            # Show stolen data
            if 'stolen_tracking_data' in st.session_state:
                self.display_stolen_data()
    
    def execute_attack_chain(self, attack_steps):
        """Execute the full attack chain with realistic timing"""
        
        self.start_time = time.time()
        self.current_step = 0
        self.steps_completed = []
        
        # Create placeholders for dynamic updates
        status_placeholder = st.empty()
        data_placeholder = st.empty()
        metrics_placeholder = st.empty()
        
        for step in attack_steps:
            self.current_step = step['id'] - 1
            
            # Update status
            st.session_state['attack_status'] = {
                'active': True,
                'current_step': step['name'],
                'action': step['description']
            }
            
            # Show progress
            with status_placeholder.container():
                st.info(f"⚡ Executing Step {step['id']}: {step['name']}")
                progress_bar = st.progress(0)
                
                # Simulate step execution with progress
                for i in range(100):
                    progress_bar.progress(i + 1)
                    time.sleep(step['duration'] / 100)
            
            # Execute specific step action
            if step['id'] == 1:
                self.execute_reconnaissance()
            elif step['id'] == 2:
                self.execute_credential_extraction()
            elif step['id'] == 3:
                self.execute_endpoint_discovery()
            elif step['id'] == 4:
                self.execute_rate_limit_test(metrics_placeholder)
            elif step['id'] == 5:
                self.execute_data_exfiltration(data_placeholder)
            
            self.steps_completed.append(step['id'])
            
            # Brief pause between steps
            time.sleep(0.5)
        
        # Final summary
        elapsed_time = time.time() - self.start_time
        
        with status_placeholder.container():
            st.success(f"""
            ✅ **Attack Chain Complete!**
            - Time elapsed: {elapsed_time:.2f} seconds
            - API calls made: {self.api_calls_made}
            - Data records stolen: {len(self.stolen_data)}
            - Estimated damage: ${self.api_calls_made * 0.05:.2f} in API costs
            """)
        
        st.session_state['attack_status']['active'] = False
    
    def execute_reconnaissance(self):
        """Step 1: Environment reconnaissance"""
        # Simulate scanning
        time.sleep(0.5)
        st.session_state['recon_data'] = {
            'environment_vars_found': ['CLIENT_ID', 'CLIENT_SECRET', 'ENVIRONMENT'],
            'config_files': ['config.json', '.env', 'mcp_config.yaml'],
            'exposed_endpoints': ['/track', '/validate', '/rate', '/ship']
        }
    
    def execute_credential_extraction(self):
        """Step 2: Extract credentials"""
        # Simulate credential extraction
        st.session_state['extracted_credentials'] = {
            'client_id': 'ups_mcp_a1b2c3d4e5f6g7h8',
            'client_secret': 'secret_k9j8h7g6f5e4d3c2b1a0z9y8x7w6v5',
            'environment': 'production',
            'endpoint': 'https://onlinetools.ups.com/api/v1'
        }
    
    def execute_endpoint_discovery(self):
        """Step 3: API endpoint discovery"""
        st.session_state['discovered_endpoints'] = {
            'tracking': '/track/v1/details',
            'address': '/addressvalidation/v1/validate',
            'rating': '/rating/v1/rate',
            'shipping': '/shipments/v1/ship'
        }
    
    def execute_rate_limit_test(self, placeholder):
        """Step 4: Rate limit testing with realistic timing"""
        
        with placeholder.container():
            st.markdown("### ⚡ Rate Limit Bypass Test")
            
            # Create columns for metrics
            col1, col2, col3 = st.columns(3)
            
            # Initialize metrics
            calls_metric = col1.metric("API Calls", "0", delta=None)
            time_metric = col2.metric("Time Elapsed", "0.0s", delta=None)
            rate_metric = col3.metric("Calls/Second", "0", delta=None)
            
            # Simulate rapid API calls
            start = time.time()
            num_calls = 1000
            
            # Update metrics in batches for realistic display
            for batch in range(10):
                batch_size = 100
                time.sleep(0.2)  # Simulate network latency
                
                self.api_calls_made += batch_size
                elapsed = time.time() - start
                rate = self.api_calls_made / elapsed if elapsed > 0 else 0
                
                # Update metrics
                col1.metric("API Calls", f"{self.api_calls_made}", delta=f"+{batch_size}")
                col2.metric("Time Elapsed", f"{elapsed:.1f}s")
                col3.metric("Calls/Second", f"{rate:.0f}", delta="No limit!")
            
            st.warning(f"""
            ⚠️ **No Rate Limiting Detected!**
            - Made {self.api_calls_made} API calls in {elapsed:.1f} seconds
            - Average rate: {rate:.0f} calls/second
            - Cost impact: ${self.api_calls_made * 0.05:.2f}
            """)
    
    def execute_data_exfiltration(self, placeholder):
        """Step 5: Data exfiltration with visual display"""
        
        generator = MockDataGenerator()
        tracking_numbers = generator.generate_tracking_numbers(50)
        
        with placeholder.container():
            st.markdown("### 📊 Live Data Exfiltration")
            
            # Create data theft visualization
            data_container = st.container()
            
            with data_container:
                st.markdown("""
                <div class="data-theft-container">
                <h4 style="color: #00ff00;">💀 EXTRACTING CUSTOMER DATA...</h4>
                </div>
                """, unsafe_allow_html=True)
                
                # Create placeholder for streaming data
                data_display = st.empty()
                
                stolen_records = []
                
                # Stream data extraction
                for i, tracking in enumerate(tracking_numbers[:20]):  # Show first 20
                    customer_data = generator.generate_customer_data(tracking)
                    stolen_records.append(customer_data)
                    self.stolen_data.append(customer_data)
                    
                    # Display streaming data
                    with data_display.container():
                        st.markdown(f"""
                        <div class="data-theft-container" style="max-height: 300px; overflow-y: auto;">
                        """, unsafe_allow_html=True)
                        
                        for record in stolen_records[-10:]:  # Show last 10 records
                            st.markdown(f"""
                            <div class="stolen-data-row">
                            📦 {record['tracking_number']}<br>
                            👤 {record['recipient']['name']}<br>
                            📧 {record['recipient']['email']}<br>
                            📍 {record['recipient']['address']}, {record['recipient']['city']}, {record['recipient']['state']}<br>
                            💰 {record['package_details']['value']}
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.markdown("</div>", unsafe_allow_html=True)
                    
                    # Add realistic delay
                    time.sleep(0.1)
                
                # Store in session state
                st.session_state['stolen_tracking_data'] = stolen_records
                
                # Show summary
                st.error(f"""
                🚨 **Data Breach Complete!**
                - Records stolen: {len(stolen_records)}
                - PII exposed: {len(stolen_records) * 2} individuals
                - Addresses leaked: {len(stolen_records)}
                - Phone numbers: {len(stolen_records) * 2}
                - Estimated GDPR fine: ${len(stolen_records) * 1000}
                """)
    
    def display_stolen_data(self):
        """Display stolen data in a table format"""
        if 'stolen_tracking_data' in st.session_state:
            st.markdown("### 🔓 Exfiltrated Customer Data")
            
            # Convert to DataFrame for display
            data = st.session_state['stolen_tracking_data']
            
            # Create summary DataFrame
            df_data = []
            for record in data[:10]:  # Show first 10
                df_data.append({
                    'Tracking #': record['tracking_number'][:10] + '***',
                    'Recipient': record['recipient']['name'],
                    'Email': record['recipient']['email'],
                    'Phone': record['recipient']['phone'],
                    'Address': f"{record['recipient']['city']}, {record['recipient']['state']}",
                    'Value': record['package_details']['value'],
                    'Status': record['status']['current']
                })
            
            df = pd.DataFrame(df_data)
            
            # Display with styling
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Tracking #": st.column_config.TextColumn("Tracking #", width="small"),
                    "Value": st.column_config.TextColumn("Value", width="small"),
                    "Status": st.column_config.TextColumn("Status", width="small")
                }
            )
            
            # Download button for "stolen" data
            csv = df.to_csv(index=False)
            st.download_button(
                label="💾 Download Stolen Data (CSV)",
                data=csv,
                file_name="stolen_ups_data.csv",
                mime="text/csv"
            )

# ============================================================================
# ENHANCED VULNERABILITY DEMO
# ============================================================================

class EnhancedVulnerabilityDemo:
    """Enhanced vulnerability demonstrations with visual feedback"""
    
    def show_live_exploitation(self):
        st.header("🔴 Live Exploitation Dashboard")
        
        tab1, tab2, tab3, tab4 = st.tabs([
            "💉 SQL Injection",
            "🔓 Credential Theft", 
            "📊 Mass Data Export",
            "💰 Cost Attack"
        ])
        
        with tab1:
            self.demonstrate_sql_injection()
        
        with tab2:
            self.demonstrate_credential_theft()
        
        with tab3:
            self.demonstrate_mass_export()
        
        with tab4:
            self.demonstrate_cost_attack()
    
    def demonstrate_sql_injection(self):
        """Live SQL injection demonstration"""
        st.markdown("### SQL Injection via Tracking Number")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Injection Payloads:**")
            
            payloads = {
                "Basic SQL": "1Z' OR '1'='1",
                "Union Select": "1Z' UNION SELECT * FROM customers--",
                "Database Dump": "1Z'; DROP TABLE shipments; --",
                "Time-based": "1Z' AND SLEEP(5)--",
                "Error-based": "1Z' AND 1=CONVERT(int, @@version)--"
            }
            
            selected_payload = st.selectbox("Select Payload", list(payloads.keys()))
            payload_value = st.text_input("Payload Value", value=payloads[selected_payload])
            
            if st.button("💉 Inject Payload", type="primary"):
                with st.spinner("Executing injection..."):
                    time.sleep(1.5)
                    
                    st.error("""
                    ❌ **INJECTION SUCCESSFUL!**
                    
                    The payload was executed directly against the database:
                    """)
                    
                    st.code(f"""
SQL Query Executed:
SELECT * FROM tracking WHERE number = '{payload_value}'

Result: Database returned all records due to:
- No input sanitization
- No prepared statements
- Direct string concatenation
                    """)
        
        with col2:
            st.markdown("**Vulnerable Code:**")
            st.code("""
# Current UPS MCP Implementation (VULNERABLE)
def track_package(inquiryNumber: str):
    # DANGER: Direct SQL query construction!
    query = f"SELECT * FROM tracking WHERE number = '{inquiryNumber}'"
    
    # No validation, no sanitization!
    results = database.execute(query)
    return results
    
# Attacker input: 1Z' OR '1'='1
# Resulting query: SELECT * FROM tracking WHERE number = '1Z' OR '1'='1'
# Result: Returns ALL records!
            """, language="python")
    
    def demonstrate_credential_theft(self):
        """Live credential extraction"""
        st.markdown("### OAuth Credential Extraction")
        
        attack_methods = {
            "Environment Variable Dump": {
                "command": "printenv | grep -E 'CLIENT|SECRET|API'",
                "result": {
                    "CLIENT_ID": "ups_mcp_prod_a1b2c3d4e5f6",
                    "CLIENT_SECRET": "sk_live_k9j8h7g6f5e4d3c2b1a0",
                    "API_KEY": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
                    "API_ENDPOINT": "https://onlinetools.ups.com/api/v1"
                }
            },
            "Process Memory Scan": {
                "command": "strings /proc/$(pgrep python)/environ",
                "result": {
                    "OAuth_Token": "oauth2_token_Xk3j9dk2jd92jd29djk29",
                    "Refresh_Token": "refresh_93jd92jd92jd92j3d92j3d9",
                    "Session_Keys": ["sess_2934j", "sess_9234k", "sess_0234j"]
                }
            },
            "Config File Access": {
                "command": "cat ~/.ups/config.json",
                "result": {
                    "production": {
                        "client_id": "ups_mcp_prod_client",
                        "client_secret": "ups_mcp_prod_secret",
                        "rate_limit": "null",
                        "audit_enabled": "false"
                    }
                }
            }
        }
        
        method = st.selectbox("Extraction Method", list(attack_methods.keys()))
        
        if st.button("🔓 Extract Credentials", type="primary"):
            with st.spinner("Extracting credentials..."):
                time.sleep(2)
                
                attack = attack_methods[method]
                
                st.markdown(f"""
                <div class="vulnerability-box">
                <h4>⚠️ Credentials Extracted Successfully!</h4>
                <p>Command executed: <code>{attack['command']}</code></p>
                </div>
                """, unsafe_allow_html=True)
                
                st.json(attack['result'])
                
                st.warning("""
                **Impact:**
                - Full API access obtained
                - Can make unlimited authenticated requests
                - Access to all customer data
                - Ability to modify shipments
                - Complete system compromise
                """)
    
    def demonstrate_mass_export(self):
        """Demonstrate mass data export"""
        st.markdown("### Mass Data Exfiltration")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            num_records = st.slider("Records to steal", 100, 10000, 1000)
            
            export_types = st.multiselect(
                "Data to export",
                ["Tracking Numbers", "Customer Names", "Addresses", "Phone Numbers", "Email Addresses", "Package Values"],
                default=["Tracking Numbers", "Customer Names", "Addresses"]
            )
            
            if st.button("📤 Start Mass Export", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                generator = MockDataGenerator()
                exported_data = []
                
                for i in range(min(num_records, 100)):  # Limit display to 100
                    progress_bar.progress((i + 1) / min(num_records, 100))
                    status_text.text(f"Exporting record {i + 1} of {num_records}...")
                    
                    tracking = generator.generate_tracking_numbers(1)[0]
                    data = generator.generate_customer_data(tracking)
                    exported_data.append(data)
                    
                    time.sleep(0.01)
                
                status_text.text(f"Export complete! {num_records} records stolen.")
                
                # Store in session
                st.session_state['mass_export_data'] = exported_data
                
                # Show sample
                st.error(f"""
                🚨 **Mass Data Breach!**
                - Records exported: {num_records}
                - Data points stolen: {num_records * len(export_types)}
                - Estimated value: ${num_records * 10}
                - GDPR violation fine: ${num_records * 100}
                """)
        
        with col2:
            if 'mass_export_data' in st.session_state:
                st.markdown("**Sample of Stolen Data:**")
                
                sample_data = st.session_state['mass_export_data'][:5]
                for idx, record in enumerate(sample_data, 1):
                    st.markdown(f"""
                    **Record {idx}:**
                    - 📦 {record['tracking_number']}
                    - 👤 {record['recipient']['name']}
                    - 📍 {record['recipient']['address']}
                    - 📧 {record['recipient']['email']}
                    - 💰 {record['package_details']['value']}
                    """)
    
    def demonstrate_cost_attack(self):
        """Demonstrate API cost attack"""
        st.markdown("### API Cost Overrun Attack")
        
        # Cost calculator
        st.markdown("**UPS API Pricing (Estimated):**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Per Request", "$0.05")
        with col2:
            st.metric("Daily Limit", "None")
        with col3:
            st.metric("Rate Limit", "None")
        
        st.markdown("---")
        
        # Attack configuration
        calls_per_second = st.slider("API Calls per Second", 10, 1000, 100)
        duration_minutes = st.slider("Attack Duration (minutes)", 1, 60, 10)
        
        total_calls = calls_per_second * duration_minutes * 60
        total_cost = total_calls * 0.05
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total API Calls", f"{total_calls:,}")
        with col2:
            st.metric("Total Cost Impact", f"${total_cost:,.2f}")
        
        if st.button("💸 Launch Cost Attack", type="primary"):
            
            # Simulate the attack
            attack_container = st.container()
            
            with attack_container:
                st.warning("⚠️ Simulating cost attack...")
                
                # Real-time metrics
                metric_cols = st.columns(4)
                calls_metric = metric_cols[0].empty()
                cost_metric = metric_cols[1].empty()
                time_metric = metric_cols[2].empty()
                rate_metric = metric_cols[3].empty()
                
                # Progress chart
                chart_placeholder = st.empty()
                
                # Simulate attack for 5 seconds (scaled down)
                start_time = time.time()
                calls_made = 0
                costs = []
                times = []
                
                for i in range(50):  # 5 seconds, 10 updates per second
                    elapsed = time.time() - start_time
                    calls_made = int(calls_per_second * elapsed)
                    current_cost = calls_made * 0.05
                    
                    # Update metrics
                    calls_metric.metric("API Calls", f"{calls_made:,}")
                    cost_metric.metric("Cost Incurred", f"${current_cost:.2f}")
                    time_metric.metric("Time Elapsed", f"{elapsed:.1f}s")
                    rate_metric.metric("Calls/Second", f"{calls_per_second}")
                    
                    # Update chart data
                    costs.append(current_cost)
                    times.append(elapsed)
                    
                    # Update chart
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=times,
                        y=costs,
                        mode='lines',
                        name='Cost',
                        line=dict(color='red', width=3)
                    ))
                    fig.update_layout(
                        title='Real-time Cost Accumulation',
                        xaxis_title='Time (seconds)',
                        yaxis_title='Cost ($)',
                        height=300
                    )
                    chart_placeholder.plotly_chart(fig, use_container_width=True)
                    
                    time.sleep(0.1)
                
                st.error(f"""
                🚨 **Attack Impact Summary:**
                - Duration: {elapsed:.1f} seconds (simulated)
                - API calls made: {calls_made:,}
                - Cost incurred: ${current_cost:.2f}
                - Projected daily cost: ${current_cost * (86400 / elapsed):.2f}
                - Monthly impact: ${current_cost * (86400 / elapsed) * 30:,.2f}
                
                **No rate limiting or cost controls detected!**
                """)

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    # Sidebar
    st.sidebar.title("🔒 UPS MCP Security Analysis")
    st.sidebar.markdown("---")
    
    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        [
            "🏠 Overview",
            "🎯 Step-by-Step Attack",
            "💀 Live Exploitation",
            "📊 Impact Analysis",
            "🛡️ Secure Gateway Solution"
        ]
    )
    
    # Session state initialization
    if 'attack_log' not in st.session_state:
        st.session_state['attack_log'] = []
    
    # Page routing
    if page == "🏠 Overview":
        show_overview()
    
    elif page == "🎯 Step-by-Step Attack":
        executor = StepByStepAttackExecutor()
        executor.show_attack_steps()
    
    elif page == "💀 Live Exploitation":
        demo = EnhancedVulnerabilityDemo()
        demo.show_live_exploitation()
    
    elif page == "📊 Impact Analysis":
        show_impact_analysis()
    
    elif page == "🛡️ Secure Gateway Solution":
        show_secure_gateway_solution()
    
    # Footer with live metrics
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📈 Live Attack Metrics")
    
    if 'api_calls_made' not in st.session_state:
        st.session_state['api_calls_made'] = 0
    if 'data_stolen' not in st.session_state:
        st.session_state['data_stolen'] = 0
    
    st.sidebar.metric("API Calls Made", st.session_state.get('api_calls_made', 0))
    st.sidebar.metric("Records Stolen", len(st.session_state.get('stolen_tracking_data', [])))
    st.sidebar.metric("Vulnerabilities Found", "15")
    st.sidebar.metric("Security Score", "F", delta="-85%", delta_color="inverse")

def show_overview():
    st.title("🚨 UPS MCP Security Vulnerability Analysis")
    
    # Alert box
    st.error("""
    ⚠️ **CRITICAL SECURITY ALERT**
    
    This demonstration reveals severe vulnerabilities in the UPS MCP implementation that allow:
    - Complete credential extraction in < 3 seconds
    - Unlimited API calls with no rate limiting
    - SQL injection through tracking parameters
    - Mass customer data exfiltration
    - Zero audit trail or monitoring
    """)
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Critical Vulnerabilities",
            value="15",
            delta="All Exploitable",
            delta_color="inverse"
        )
    
    with col2:
        st.metric(
            label="Attack Success Rate",
            value="100%",
            delta="No Protection",
            delta_color="inverse"
        )
    
    with col3:
        st.metric(
            label="Data at Risk",
            value="ALL",
            delta="Unlimited Access",
            delta_color="inverse"
        )
    
    with col4:
        st.metric(
            label="Time to Compromise",
            value="< 5 sec",
            delta="Instant",
            delta_color="inverse"
        )
    
    st.markdown("---")
    
    # Show vulnerable vs secure architecture
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🔓 Current UPS MCP (Vulnerable)")
        st.code("""
┌─────────────┐
│  AI Agent   │ ← No Authentication
└──────┬──────┘
       │ 
       ▼ Direct Access
┌─────────────┐
│  MCP Server │ ← No Validation
├─────────────┤
│ CLIENT_ID   │ ← Plaintext
│ CLIENT_SEC  │ ← Exposed
└──────┬──────┘
       │
       ▼ Unprotected
┌─────────────┐
│   UPS API   │ ← No Rate Limit
└─────────────┘

Vulnerabilities:
❌ Credentials in environment vars
❌ No input validation
❌ No rate limiting
❌ No audit logging
❌ No anomaly detection
        """)
    
    with col2:
        st.markdown("### 🔒 Your Secure Gateway")
        st.code("""
┌─────────────┐
│  AI Agent   │ ← JWT Auth Required
└──────┬──────┘
       │
       ▼ Validated
┌─────────────┐
│   Gateway   │ ← Multi-layer Security
├─────────────┤
│ Validation  │ ← Input Sanitization
│ Rate Limit  │ ← Request Throttling
│ Encryption  │ ← AES-256
│ Audit Log   │ ← Complete Trail
└──────┬──────┘
       │
       ▼ Protected
┌─────────────┐
│   UPS API   │ ← Secured
└─────────────┘

Protection:
✅ Encrypted credential vault
✅ SQL injection prevention
✅ Rate limiting per agent
✅ Full audit trail
✅ ML anomaly detection
        """)

def show_impact_analysis():
    st.title("📊 Security Impact Analysis")
    
    # Create sample data for visualizations
    generator = MockDataGenerator()
    
    # Vulnerability distribution
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Vulnerability Severity Distribution")
        
        severity_data = pd.DataFrame({
            'Severity': ['Critical', 'High', 'Medium', 'Low'],
            'Count': [8, 5, 2, 0],
            'Color': ['#e74c3c', '#f39c12', '#f1c40f', '#2ecc71']
        })
        
        fig = px.pie(
            severity_data,
            values='Count',
            names='Severity',
            color='Severity',
            color_discrete_map={
                'Critical': '#e74c3c',
                'High': '#f39c12',
                'Medium': '#f1c40f',
                'Low': '#2ecc71'
            }
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### Attack Success Timeline")
        
        # Generate timeline data
        timeline_data = []
        for i in range(24):
            timeline_data.append({
                'Hour': i,
                'Successful Attacks': random.randint(50, 200),
                'Blocked Attacks': 0  # None blocked in current implementation
            })
        
        df_timeline = pd.DataFrame(timeline_data)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_timeline['Hour'],
            y=df_timeline['Successful Attacks'],
            mode='lines+markers',
            name='Successful Attacks',
            line=dict(color='red', width=3)
        ))
        fig.add_trace(go.Scatter(
            x=df_timeline['Hour'],
            y=df_timeline['Blocked Attacks'],
            mode='lines',
            name='Blocked Attacks',
            line=dict(color='green', width=3)
        ))
        
        fig.update_layout(
            title='24-Hour Attack Pattern',
            xaxis_title='Hour of Day',
            yaxis_title='Number of Attacks',
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Cost impact
    st.markdown("### 💰 Financial Impact Analysis")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("API Cost Overrun", "$47,500", delta="+$12,300/day")
    with col2:
        st.metric("GDPR Violation Fine", "$2.3M", delta="Per incident")
    with col3:
        st.metric("Data Breach Cost", "$4.88M", delta="Industry average")
    
    # Compliance violations
    st.markdown("### ⚖️ Compliance Violations")
    
    compliance_data = {
        'Regulation': ['GDPR', 'CCPA', 'HIPAA', 'PCI DSS', 'SOC 2'],
        'Status': ['❌ Non-compliant', '❌ Non-compliant', '❌ Non-compliant', '❌ Non-compliant', '❌ Non-compliant'],
        'Violations': [8, 6, 4, 7, 9],
        'Risk Level': ['Critical', 'Critical', 'High', 'Critical', 'Critical']
    }
    
    df_compliance = pd.DataFrame(compliance_data)
    st.dataframe(df_compliance, use_container_width=True, hide_index=True)

def show_secure_gateway_solution():
    st.title("🛡️ Secure AI Gateway Solution")
    
    st.success("""
    ✅ **Your Secure Gateway Blocks 100% of Demonstrated Attacks**
    
    Implementation provides comprehensive protection through multiple security layers.
    """)
    
    # Security features comparison
    st.markdown("### Security Features Comparison")
    
    comparison_data = {
        'Feature': [
            'Authentication',
            'Input Validation',
            'Rate Limiting',
            'Encryption',
            'Audit Logging',
            'Anomaly Detection',
            'Session Management',
            'Prompt Injection Defense',
            'Cost Controls',
            'Compliance Support'
        ],
        'UPS MCP (Current)': ['❌', '❌', '❌', '❌', '❌', '❌', '❌', '❌', '❌', '❌'],
        'Your Secure Gateway': ['✅', '✅', '✅', '✅', '✅', '✅', '✅', '✅', '✅', '✅']
    }
    
    df_comparison = pd.DataFrame(comparison_data)
    st.dataframe(df_comparison, use_container_width=True, hide_index=True)
    
    # Implementation roadmap
    st.markdown("### Implementation Roadmap")
    
    roadmap_items = [
        ("Week 1", "Deploy Gateway Infrastructure", "Set up secure cloud environment"),
        ("Week 2", "Implement Security Layers", "Add authentication, validation, rate limiting"),
        ("Week 3", "Integration Testing", "Connect with UPS APIs securely"),
        ("Week 4", "Migration", "Move from direct MCP to secure gateway"),
        ("Week 5", "Monitoring", "Enable real-time threat detection"),
        ("Week 6", "Go Live", "Full production deployment")
    ]
    
    for week, title, description in roadmap_items:
        st.markdown(f"""
        **{week}: {title}**
        - {description}
        """)
    
    # ROI calculation
    st.markdown("### Return on Investment")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Costs Avoided:**")
        st.metric("API Overrun Prevention", "$570,000/year")
        st.metric("Data Breach Prevention", "$4.88M")
        st.metric("Compliance Fines Avoided", "$2.3M")
    
    with col2:
        st.markdown("**Investment Required:**")
        st.metric("Implementation Cost", "$150,000")
        st.metric("Annual Maintenance", "$50,000")
        st.metric("ROI", "3,200%", delta="First Year")

if __name__ == "__main__":
    main()
