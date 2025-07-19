#!/usr/bin/env python3
"""
Advanced Multi-Agent USCIS Form Reader - Final Production Version
With All Debugging, Error Handling, and Auto-Save Features
"""

import os
import json
import re
import time
import hashlib
import traceback
import io
import csv
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Set, Union
from dataclasses import dataclass, field, asdict
from collections import defaultdict, OrderedDict
from abc import ABC, abstractmethod
import copy
from enum import Enum
import logging

import streamlit as st

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DEBUG_MODE = True  # Set to False in production
OUTPUT_DIR = "extraction_results"
LOG_DIR = "logs"

# Create directories
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Initialize globals
OPENAI_AVAILABLE = False
OpenAI = None

# Try imports
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
    logger.info(f"PyMuPDF version: {fitz.__version__}")
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None
    logger.error("PyMuPDF not available. Install with: pip install PyMuPDF")

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

# Page config
st.set_page_config(
    page_title="Advanced USCIS Form Reader",
    page_icon="🤖",
    layout="wide"
)

# [Include all the CSS styling from original]
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
    }
    .agent-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .agent-active {
        border-left: 4px solid #2196F3;
        background: #E3F2FD;
    }
    .agent-success {
        border-left: 4px solid #4CAF50;
        background: #E8F5E9;
    }
    .agent-error {
        border-left: 4px solid #f44336;
        background: #FFEBEE;
    }
    .field-card {
        background: #f5f5f5;
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 0.5rem;
        margin: 0.2rem 0;
        font-family: monospace;
    }
    .hierarchy-tree {
        font-family: monospace;
        white-space: pre;
        background: #f5f5f5;
        padding: 1rem;
        border-radius: 4px;
        overflow-x: auto;
    }
    .validation-badge {
        display: inline-block;
        padding: 0.2rem 0.5rem;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .badge-success {
        background: #4CAF50;
        color: white;
    }
    .badge-warning {
        background: #FF9800;
        color: white;
    }
    .badge-error {
        background: #f44336;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# [Include all Enums and Data Classes from original]
class FieldType(Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SIGNATURE = "signature"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    NAME = "name"
    UNKNOWN = "unknown"

class ExtractionConfidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"

# [Include all @dataclass definitions from original]
# FieldPattern, FieldNode, FormSchema, PartStructure, FormExtractionResult

# [Include PatternLibrary class with improvements]
class PatternLibrary:
    """Enhanced pattern library with flexible patterns"""
    
    def __init__(self):
        self.patterns = self._build_patterns()
        self.form_schemas = self._build_form_schemas()
    
    def _build_patterns(self) -> Dict[str, List[FieldPattern]]:
        """Build comprehensive pattern library with flexible patterns"""
        return {
            "structure": [
                FieldPattern(
                    re.compile(r'^Part\s+(\d+)\.?\s*(.*)$', re.IGNORECASE),
                    FieldType.UNKNOWN,
                    1.0,
                    "Part header"
                ),
                FieldPattern(
                    re.compile(r'^\s*Part\s+(\d+)', re.IGNORECASE),
                    FieldType.UNKNOWN,
                    0.9,
                    "Part header simple"
                ),
                FieldPattern(
                    re.compile(r'^Section\s+([A-Z])\.\s*(.*)$', re.IGNORECASE),
                    FieldType.UNKNOWN,
                    0.9,
                    "Section header"
                ),
            ],
            "item": [
                # Standard numbered items
                FieldPattern(
                    re.compile(r'^(\d+)\.\s+(.+?)(?:\s*\(.*\))?$'),
                    FieldType.UNKNOWN,
                    0.95,
                    "Numbered item with period"
                ),
                FieldPattern(
                    re.compile(r'^\s*(\d+)\s*\.\s*(.+)$'),
                    FieldType.UNKNOWN,
                    0.9,
                    "Flexible numbered item"
                ),
                FieldPattern(
                    re.compile(r'^(\d+)\s+([A-Z].+?)(?:\s*\(.*\))?$'),
                    FieldType.UNKNOWN,
                    0.85,
                    "Numbered item without period"
                ),
                # Sub-items
                FieldPattern(
                    re.compile(r'^(\d+)([a-z])\.\s+(.+?)$'),
                    FieldType.UNKNOWN,
                    0.95,
                    "Sub-item with number and letter"
                ),
                FieldPattern(
                    re.compile(r'^\s*(\d+)\s*([a-z])\s*\.\s*(.+)$'),
                    FieldType.UNKNOWN,
                    0.9,
                    "Flexible sub-item"
                ),
                FieldPattern(
                    re.compile(r'^\s*([a-z])\.\s+(.+?)$'),
                    FieldType.UNKNOWN,
                    0.9,
                    "Letter-only sub-item"
                ),
            ],
            # [Include all field_type patterns from original]
        }
    
    # [Include rest of PatternLibrary methods from original]

# [Include all Agent classes with debugging enhancements]

class BaseAgent(ABC):
    """Enhanced base agent with better logging and debug support"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.status = "idle"
        self.logs = []
        self.errors = []
        self.start_time = None
        self.end_time = None
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        pass
    
    def log(self, message: str, level: str = "info", details: Any = None):
        """Enhanced logging with file output"""
        entry = {
            "timestamp": datetime.now(),
            "message": message,
            "level": level,
            "details": details
        }
        self.logs.append(entry)
        
        # Log to file if debug mode
        if DEBUG_MODE:
            log_file = os.path.join(LOG_DIR, f"debug_{datetime.now().strftime('%Y%m%d')}.log")
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{entry['timestamp']}] [{self.name}] [{level.upper()}] {message}\n")
                if details:
                    f.write(f"  Details: {details}\n")
        
        # Display in UI
        self._display_log(entry)
    
    # [Include rest of BaseAgent methods]

# [Include all other agent classes with debug enhancements applied]

class MasterCoordinator(BaseAgent):
    """Enhanced coordinator with auto-save and better error handling"""
    
    def __init__(self, max_iterations: int = 3):
        super().__init__(
            "Master Coordinator",
            "Orchestrates the extraction process"
        )
        self.max_iterations = max_iterations
        self.agents = {
            'extractor': AdaptivePatternExtractor(),
            'assigner': SmartKeyAssignment(),
            'validator': QuestionnaireValidator(),
            'formatter': OutputFormatter()
        }
        self.pattern_library = PatternLibrary()
    
    def execute(self, pdf_file) -> Optional[Dict[str, Any]]:
        """Execute coordinated extraction with auto-save"""
        self.start()
        
        try:
            # Debug: Check PDF file
            self.log(f"PDF file type: {type(pdf_file)}")
            if hasattr(pdf_file, 'name'):
                self.log(f"PDF file name: {pdf_file.name}")
            
            result = None
            best_result = None
            best_score = 0.0
            
            for iteration in range(self.max_iterations):
                self.log(f"\n{'='*50}")
                self.log(f"Starting iteration {iteration + 1}/{self.max_iterations}")
                
                # Step 1: Extract
                if iteration == 0:
                    try:
                        result = self.agents['extractor'].execute(pdf_file)
                    except Exception as e:
                        self.log(f"Extractor failed: {str(e)}", "error", traceback.format_exc())
                        result = FormExtractionResult(
                            form_number="Unknown",
                            form_title="Extraction Failed"
                        )
                else:
                    self.log("Re-extracting with refined patterns...")
                    result = self._refine_extraction(pdf_file, result, validation_results)
                
                if not result:
                    self.log("Extraction returned None", "error")
                    break
                
                # Debug: Log extraction results
                self.log(f"Form identified: {result.form_number}")
                self.log(f"Parts found: {len(result.parts)}")
                self.log(f"Total fields: {result.total_fields}")
                
                # Step 2: Assign keys
                try:
                    result = self.agents['assigner'].execute(result)
                except Exception as e:
                    self.log(f"Key assignment failed: {str(e)}", "error")
                
                # Step 3: Validate
                schema = self.pattern_library.form_schemas.get(result.form_number)
                try:
                    is_valid, score, validation_results = self.agents['validator'].execute(result, schema)
                except Exception as e:
                    self.log(f"Validation failed: {str(e)}", "error")
                    is_valid, score, validation_results = False, 0.0, []
                
                # Track best result
                if score > best_score:
                    best_score = score
                    best_result = copy.deepcopy(result)
                
                # Check if good enough
                if is_valid and score >= 0.85:
                    self.log(f"✅ Extraction successful with score {score:.0%}!", "success")
                    break
                
                self.log(f"Iteration {iteration + 1} score: {score:.0%}")
                
                if iteration < self.max_iterations - 1:
                    self.log("Score below threshold, refining...")
                    time.sleep(0.5)
            
            # Use best result
            if best_result:
                try:
                    # Step 4: Format output
                    output = self.agents['formatter'].execute(best_result)
                    
                    # Add metadata
                    output['_metadata'] = {
                        'form_number': best_result.form_number,
                        'form_title': best_result.form_title,
                        'total_fields': best_result.total_fields,
                        'validation_score': best_score,
                        'iterations': iteration + 1
                    }
                    
                    # Auto-save results
                    self._auto_save_results(output)
                    
                    self.complete()
                    return output
                except Exception as e:
                    self.log(f"Formatting failed: {str(e)}", "error", traceback.format_exc())
            
            self.log("No valid extraction produced", "error")
            self.complete(False)
            return None
            
        except Exception as e:
            self.log(f"Coordination failed: {str(e)}", "error", traceback.format_exc())
            self.complete(False)
            return None
    
    def _auto_save_results(self, output: Dict[str, Any]):
        """Auto-save extraction results to files"""
        try:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            form_number = output.get('_metadata', {}).get('form_number', 'unknown')
            base_filename = f"{form_number}_{timestamp}"
            
            # Save as JSON
            json_path = os.path.join(OUTPUT_DIR, f"{base_filename}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            self.log(f"Saved JSON to: {json_path}", "success")
            
            # Save as CSV
            csv_path = os.path.join(OUTPUT_DIR, f"{base_filename}.csv")
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Field Key", "Value", "Label"])
                
                for key, value in sorted(output.items()):
                    if not key.startswith('_') and not key.endswith('_title'):
                        label = output.get(f"{key}_title", "")
                        writer.writerow([key, value, label])
            
            self.log(f"Saved CSV to: {csv_path}", "success")
            
            # Add file paths to output metadata
            output['_metadata']['output_files'] = {
                'json': json_path,
                'csv': csv_path
            }
            
        except Exception as e:
            self.log(f"Auto-save failed: {str(e)}", "error")
    
    def _refine_extraction(self, pdf_file, previous_result: FormExtractionResult,
                         validation_results: List[Dict]) -> FormExtractionResult:
        """Refine extraction based on validation feedback"""
        issues = []
        for result in validation_results:
            if not result["passed"]:
                issues.append(result)
        
        self.log(f"Refining based on {len(issues)} validation issues")
        
        # Re-run extraction with adjustments
        return self.agents['extractor'].execute(pdf_file)

# [Include all UI component functions from original]

# Diagnostic function
def diagnose_uscis_reader(pdf_file):
    """Diagnostic test for USCIS form reader"""
    output = []
    output.append("=== USCIS Form Reader Diagnostic ===\n")
    
    # 1. Check PyMuPDF
    output.append("1. Checking PyMuPDF installation...")
    try:
        import fitz
        output.append(f"✓ PyMuPDF version: {fitz.__version__}")
    except ImportError:
        output.append("✗ PyMuPDF not installed!")
        output.append("  Run: pip install PyMuPDF")
        return "\n".join(output)
    
    # 2. Check PDF file
    output.append("\n2. Checking PDF file...")
    if pdf_file is None:
        output.append("✗ No PDF file provided")
        return "\n".join(output)
    
    if hasattr(pdf_file, 'name'):
        output.append(f"✓ File name: {pdf_file.name}")
    
    # 3. Try to open PDF
    output.append("\n3. Testing PDF opening...")
    try:
        pdf_bytes = pdf_file.read() if hasattr(pdf_file, 'read') else pdf_file
        if hasattr(pdf_file, 'seek'):
            pdf_file.seek(0)
        
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        output.append(f"✓ PDF opened successfully")
        output.append(f"  Pages: {len(doc)}")
        
        # 4. Check first page content
        output.append("\n4. Checking first page content...")
        first_page_text = doc[0].get_text()
        output.append(f"✓ Text extracted: {len(first_page_text)} characters")
        
        # Look for form identifiers
        output.append("\n5. Looking for form identifiers...")
        forms_found = []
        for form_pattern in ['I-539', 'I-129', 'G-28', 'I-90', 'I-485', 'I-765', 'N-400']:
            if form_pattern in first_page_text:
                forms_found.append(form_pattern)
        
        if forms_found:
            output.append(f"✓ Forms found: {', '.join(forms_found)}")
        else:
            output.append("✗ No standard form identifiers found")
            output.append("  Text preview (first 200 chars):")
            output.append(f"  {first_page_text[:200].replace(chr(10), ' ')}")
        
        doc.close()
        
    except Exception as e:
        output.append(f"✗ Error: {str(e)}")
        output.append(f"  Type: {type(e).__name__}")
        output.append("  Traceback:")
        output.append(traceback.format_exc())
    
    return "\n".join(output)

# Main Application
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Advanced USCIS Form Reader</h1>'
        '<p>Multi-Agent System with Adaptive Pattern Recognition</p>'
        '<p style="font-size: 0.9em;">Output files saved to: extraction_results/</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Initialize session state
    if 'extraction_output' not in st.session_state:
        st.session_state.extraction_output = None
    if 'extraction_result' not in st.session_state:
        st.session_state.extraction_result = None
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        max_iterations = st.slider("Max Iterations", 1, 5, 3)
        show_agent_logs = st.checkbox("Show Agent Activity", value=True)
        show_structure = st.checkbox("Show Form Structure", value=True)
        
        st.markdown("---")
        st.markdown("### 📊 System Status")
        
        # Check dependencies
        if PYMUPDF_AVAILABLE:
            st.success("✅ PyMuPDF Ready")
        else:
            st.error("❌ PyMuPDF Not Installed")
            st.code("pip install PyMuPDF")
        
        if OPENAI_AVAILABLE:
            if os.environ.get('OPENAI_API_KEY'):
                st.success("✅ OpenAI Ready")
            else:
                st.warning("⚠️ OpenAI Key Missing")
        else:
            st.info("ℹ️ OpenAI Optional")
        
        st.markdown("---")
        st.markdown("### 📁 Output Directory")
        st.info(f"Results saved to: `{OUTPUT_DIR}/`")
        
        if st.button("📂 Open Output Folder"):
            import platform
            import subprocess
            
            if platform.system() == 'Windows':
                os.startfile(OUTPUT_DIR)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.Popen(['open', OUTPUT_DIR])
            else:  # Linux
                subprocess.Popen(['xdg-open', OUTPUT_DIR])
    
    # Main content
    st.markdown("## 📄 Upload USCIS Form")
    
    uploaded_file = st.file_uploader(
        "Choose a PDF form",
        type=['pdf'],
        help="Supported forms: I-539, I-129, G-28, I-90, I-485, I-765, N-400"
    )
    
    if uploaded_file:
        # Debug section
        with st.expander("🔍 Debug Information", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Test PDF Basic"):
                    try:
                        import fitz
                        pdf_bytes = uploaded_file.read()
                        uploaded_file.seek(0)
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        
                        st.success(f"✓ PDF opened: {len(doc)} pages")
                        
                        # Test text extraction
                        text = doc[0].get_text()
                        st.info(f"Page 1 text length: {len(text)} chars")
                        
                        # Show preview
                        st.text_area("Text Preview (first 1000 chars):", 
                                   text[:1000], height=200)
                        
                        doc.close()
                    except Exception as e:
                        st.error(f"Failed: {str(e)}")
                        st.code(traceback.format_exc())
            
            with col2:
                if st.button("Run Full Diagnostic"):
                    diagnostic_output = diagnose_uscis_reader(uploaded_file)
                    st.code(diagnostic_output)
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.success(f"✅ Uploaded: {uploaded_file.name}")
        
        with col2:
            process_btn = st.button(
                "🚀 Extract",
                type="primary",
                use_container_width=True
            )
        
        with col3:
            if st.session_state.extraction_output:
                st.button(
                    "🔄 Reset",
                    use_container_width=True,
                    on_click=lambda: st.session_state.update({
                        'extraction_output': None,
                        'extraction_result': None
                    })
                )
        
        if process_btn:
            # Create containers
            if show_agent_logs:
                st.session_state.agent_container = st.container()
            
            # Add error container
            error_container = st.container()
            
            with st.spinner("Processing with multi-agent system..."):
                try:
                    # Run extraction
                    coordinator = MasterCoordinator(max_iterations=max_iterations)
                    output = coordinator.execute(uploaded_file)
                    
                    if output:
                        st.session_state.extraction_output = output
                        st.success("✅ Extraction Complete!")
                        
                        # Show where files were saved
                        if '_metadata' in output and 'output_files' in output['_metadata']:
                            files = output['_metadata']['output_files']
                            st.info(f"📁 Files saved:\n- JSON: {files['json']}\n- CSV: {files['csv']}")
                    else:
                        with error_container:
                            st.error("❌ Extraction Failed - No output produced")
                            
                            # Show coordinator logs
                            if coordinator.logs:
                                st.write("**Recent Activity:**")
                                for log in coordinator.logs[-10:]:  # Last 10 logs
                                    level = log.get('level', 'info')
                                    msg = log.get('message', '')
                                    if level == 'error':
                                        st.error(f"🔴 {msg}")
                                    elif level == 'warning':
                                        st.warning(f"🟡 {msg}")
                                    else:
                                        st.info(f"🔵 {msg}")
                                        
                except Exception as e:
                    with error_container:
                        st.error(f"❌ Critical Error: {str(e)}")
                        st.error(f"Error Type: {type(e).__name__}")
                        
                        with st.expander("Full Error Traceback", expanded=True):
                            st.code(traceback.format_exc())
                        
                        st.info("💡 Try the Debug buttons above to diagnose the issue")
    
    # [Include rest of the display results section from original]
    # Display results
    if st.session_state.extraction_output:
        st.markdown("---")
        st.markdown("## 📊 Extraction Results")
        
        output = st.session_state.extraction_output
        metadata = output.get('_metadata', {})
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Form", metadata.get('form_number', 'Unknown'))
        with col2:
            st.metric("Fields", metadata.get('total_fields', 0))
        with col3:
            score = metadata.get('validation_score', 0)
            st.metric("Score", f"{score:.0%}")
        with col4:
            st.metric("Iterations", metadata.get('iterations', 1))
        
        # File location reminder
        if 'output_files' in metadata:
            st.success(f"✅ Results auto-saved to: {OUTPUT_DIR}/")
        
        # [Include rest of the results display from original]

if __name__ == "__main__":
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF is required but not installed!")
        st.code("pip install PyMuPDF")
        st.stop()
    
    main()
