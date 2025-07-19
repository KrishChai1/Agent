#!/usr/bin/env python3
"""
Advanced Multi-Agent USCIS Form Reader with Database Mapping
Complete Agentic Architecture with all Original Agents + New Mapping Agents
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

import streamlit as st

# Initialize globals
OPENAI_AVAILABLE = False
OpenAI = None

# Try imports
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    fitz = None

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

# CSS Styling
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
    .mapped-field {
        background: #E8F5E9;
        border-left: 4px solid #4CAF50;
    }
    .unmapped-field {
        background: #FFF3E0;
        border-left: 4px solid #FF9800;
    }
    .mapping-agent {
        border-left: 4px solid #9C27B0;
        background: #F3E5F5;
    }
</style>
""", unsafe_allow_html=True)

# ===== ENUMS =====
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

class MappingStatus(Enum):
    MAPPED = "mapped"
    UNMAPPED = "unmapped"
    MANUAL = "manual"
    QUESTIONNAIRE = "questionnaire"

# ===== ENHANCED DATA CLASSES =====
@dataclass
class FieldPattern:
    """Pattern for field recognition"""
    pattern: re.Pattern
    field_type: FieldType
    confidence: float = 1.0
    description: str = ""

@dataclass
class FieldNode:
    """Enhanced field node with mapping support"""
    # Core properties
    item_number: str
    label: str
    field_type: FieldType = FieldType.UNKNOWN
    value: str = ""
    
    # Hierarchy
    parent: Optional['FieldNode'] = None
    children: List['FieldNode'] = field(default_factory=list)
    
    # Location
    page: int = 1
    part_number: int = 1
    part_name: str = "Part 1"
    bbox: Optional[Tuple[float, float, float, float]] = None
    
    # Generated key
    key: str = ""
    
    # Extraction metadata
    confidence: ExtractionConfidence = ExtractionConfidence.LOW
    extraction_method: str = ""
    raw_text: str = ""
    patterns_matched: List[str] = field(default_factory=list)
    
    # Validation
    is_required: bool = False
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    
    # Mapping metadata
    mapping_status: MappingStatus = MappingStatus.UNMAPPED
    mapped_to: Optional[str] = None
    mapping_confidence: float = 0.0
    
    def add_child(self, child: 'FieldNode'):
        """Add child node"""
        child.parent = self
        self.children.append(child)
    
    def get_full_path(self) -> str:
        """Get full hierarchical path"""
        if self.parent:
            return f"{self.parent.get_full_path()}.{self.item_number}"
        return self.item_number
    
    def get_depth(self) -> int:
        """Get depth in hierarchy"""
        if self.parent:
            return self.parent.get_depth() + 1
        return 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "key": self.key,
            "item_number": self.item_number,
            "label": self.label,
            "type": self.field_type.value,
            "value": self.value,
            "confidence": self.confidence.value,
            "page": self.page,
            "mapping_status": self.mapping_status.value,
            "mapped_to": self.mapped_to,
            "children": [child.to_dict() for child in self.children]
        }

@dataclass
class FieldMapping:
    """Represents a mapping between PDF field and database field"""
    pdf_field_key: str
    pdf_field_label: str
    database_table: str
    database_field: str
    transformation: Optional[str] = None
    confidence: float = 0.0

@dataclass
class DatabaseSchema:
    """Database schema definition"""
    tables: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.tables:
            self.tables = {
                "beneficiary": {
                    "firstName": "string",
                    "lastName": "string",
                    "middleName": "string",
                    "dateOfBirth": "date",
                    "alienNumber": "string",
                    "socialSecurityNumber": "string",
                    "countryOfBirth": "string",
                    "countryOfCitizenship": "string"
                },
                "address": {
                    "streetNumber": "string",
                    "streetName": "string",
                    "aptNumber": "string",
                    "city": "string",
                    "state": "string",
                    "zipCode": "string",
                    "country": "string"
                },
                "contact": {
                    "daytimePhone": "string",
                    "mobilePhone": "string",
                    "emailAddress": "string"
                },
                "immigration": {
                    "currentStatus": "string",
                    "statusExpirationDate": "date",
                    "i94Number": "string",
                    "passportNumber": "string",
                    "passportCountry": "string",
                    "passportExpiration": "date",
                    "lastEntryDate": "date",
                    "lastEntryPort": "string"
                }
            }

@dataclass
class FormSchema:
    """Schema definition for a form"""
    form_number: str
    form_title: str
    parts: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    field_patterns: Dict[str, FieldPattern] = field(default_factory=dict)
    
    def get_expected_structure(self) -> Dict:
        """Get expected structure"""
        return {
            "form_number": self.form_number,
            "parts": self.parts,
            "required_fields": self.required_fields
        }

@dataclass
class PartStructure:
    """Represents a part with hierarchical fields"""
    part_number: int
    part_name: str
    part_title: str = ""
    root_fields: List[FieldNode] = field(default_factory=list)
    
    def get_all_fields_flat(self) -> List[FieldNode]:
        """Get all fields in flat list"""
        fields = []
        
        def collect_fields(node: FieldNode):
            fields.append(node)
            for child in node.children:
                collect_fields(child)
        
        for root in self.root_fields:
            collect_fields(root)
        
        return fields
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "part_number": self.part_number,
            "part_name": self.part_name,
            "part_title": self.part_title,
            "fields": [field.to_dict() for field in self.root_fields]
        }

@dataclass
class FormExtractionResult:
    """Complete extraction result with mapping support"""
    form_number: str
    form_title: str
    parts: Dict[int, PartStructure] = field(default_factory=dict)
    
    # Validation status
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)
    validation_score: float = 0.0
    
    # Extraction metadata
    extraction_iterations: int = 0
    total_fields: int = 0
    
    # Mapping metadata
    mapped_fields: Dict[str, FieldMapping] = field(default_factory=dict)
    unmapped_fields: List[str] = field(default_factory=list)
    mapping_completeness: float = 0.0
    
    def get_all_fields_with_keys(self) -> Dict[str, FieldNode]:
        """Get all fields indexed by key"""
        fields = {}
        for part in self.parts.values():
            for field in part.get_all_fields_flat():
                if field.key:
                    fields[field.key] = field
        return fields
    
    def to_output_format(self) -> Dict[str, Any]:
        """Convert to expected output format"""
        output = {}
        for part in self.parts.values():
            for field in part.get_all_fields_flat():
                if field.key:
                    output[field.key] = field.value
                    # Add title fields
                    if field.label:
                        output[f"{field.key}_title"] = field.label
        return output

# ===== PATTERN LIBRARY =====
class PatternLibrary:
    """Library of extraction patterns"""
    
    def __init__(self):
        self.patterns = self._build_patterns()
        self.form_schemas = self._build_form_schemas()
        self.mapping_patterns = self._build_mapping_patterns()
    
    def _build_patterns(self) -> Dict[str, List[FieldPattern]]:
        """Build comprehensive pattern library"""
        # [Include all your original patterns here]
        return {
            "structure": [
                FieldPattern(
                    re.compile(r'^Part\s+(\d+)\.?\s*(.*)$', re.IGNORECASE),
                    FieldType.UNKNOWN,
                    1.0,
                    "Part header"
                ),
                FieldPattern(
                    re.compile(r'^Section\s+([A-Z])\.\s*(.*)$', re.IGNORECASE),
                    FieldType.UNKNOWN,
                    0.9,
                    "Section header"
                ),
            ],
            # [Include all other patterns from your original code]
        }
    
    def _build_mapping_patterns(self) -> Dict[str, Tuple[str, str, float]]:
        """Build patterns for database mapping"""
        return {
            # Name mappings
            r'family.*name|last.*name': ('beneficiary', 'lastName', 0.95),
            r'given.*name|first.*name': ('beneficiary', 'firstName', 0.95),
            r'middle.*name': ('beneficiary', 'middleName', 0.9),
            
            # Number mappings
            r'a.*number|alien.*number': ('beneficiary', 'alienNumber', 0.95),
            r'ssn|social.*security': ('beneficiary', 'socialSecurityNumber', 0.95),
            r'passport.*number': ('immigration', 'passportNumber', 0.9),
            r'i.*94.*number': ('immigration', 'i94Number', 0.9),
            
            # Date mappings
            r'date.*birth|birth.*date': ('beneficiary', 'dateOfBirth', 0.95),
            r'expir.*date|status.*expir': ('immigration', 'statusExpirationDate', 0.9),
            
            # Address mappings
            r'street.*number.*name|street.*address': ('address', 'streetName', 0.9),
            r'apt|suite|ste': ('address', 'aptNumber', 0.85),
            r'city|town': ('address', 'city', 0.9),
            r'state': ('address', 'state', 0.85),
            r'zip.*code': ('address', 'zipCode', 0.9),
            
            # Contact mappings
            r'daytime.*phone': ('contact', 'daytimePhone', 0.9),
            r'mobile.*phone|cell': ('contact', 'mobilePhone', 0.9),
            r'email.*address': ('contact', 'emailAddress', 0.95),
        }
    
    def _build_form_schemas(self) -> Dict[str, FormSchema]:
        """Build form schemas"""
        # [Include all your original form schemas]
        schemas = {}
        
        # I-539 Schema
        schemas["I-539"] = FormSchema(
            form_number="I-539",
            form_title="Application to Extend/Change Nonimmigrant Status",
            parts={
                # [Include your complete schema]
            },
            required_fields=["P1_1a", "P1_1b", "P1_2", "P1_3"]
        )
        
        return schemas
    
    def get_patterns_for_context(self, context: str) -> List[FieldPattern]:
        """Get relevant patterns for context"""
        relevant_patterns = []
        
        for category, patterns in self.patterns.items():
            if category == context or context == "all":
                relevant_patterns.extend(patterns)
        
        return sorted(relevant_patterns, key=lambda p: p.confidence, reverse=True)

# ===== BASE AGENT CLASS =====
class BaseAgent(ABC):
    """Enhanced base agent with better logging"""
    
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
        """Enhanced logging"""
        entry = {
            "timestamp": datetime.now(),
            "message": message,
            "level": level,
            "details": details
        }
        self.logs.append(entry)
        
        # Display in UI
        self._display_log(entry)
    
    def _display_log(self, entry: Dict):
        """Display log in UI"""
        if hasattr(st.session_state, 'agent_container'):
            with st.session_state.agent_container:
                css_class = "agent-card"
                if entry["level"] == "error":
                    css_class += " agent-error"
                elif entry["level"] == "success":
                    css_class += " agent-success"
                elif self.status == "active":
                    css_class += " agent-active"
                elif "mapping" in self.name.lower():
                    css_class += " mapping-agent"
                
                st.markdown(
                    f'<div class="{css_class}">'
                    f'<strong>{self.name}</strong>: {entry["message"]}'
                    f'</div>', 
                    unsafe_allow_html=True
                )
    
    def start(self):
        """Start agent execution"""
        self.status = "active"
        self.start_time = datetime.now()
        self.log(f"Starting {self.description}")
    
    def complete(self, success: bool = True):
        """Complete agent execution"""
        self.end_time = datetime.now()
        duration = (self.end_time - self.start_time).total_seconds()
        
        if success:
            self.status = "completed"
            self.log(f"Completed successfully in {duration:.2f}s", "success")
        else:
            self.status = "error"
            self.log(f"Failed after {duration:.2f}s", "error")

# ===== ORIGINAL EXTRACTION AGENTS =====
# [Include all your original agents here: AdaptivePatternExtractor, SmartKeyAssignment, etc.]

# ===== NEW MAPPING AGENTS =====

class DatabaseMappingAgent(BaseAgent):
    """Agent for mapping extracted fields to database schema"""
    
    def __init__(self):
        super().__init__(
            "Database Mapping Agent",
            "Maps extracted fields to database schema using intelligent patterns"
        )
        self.pattern_library = PatternLibrary()
        self.database_schema = DatabaseSchema()
    
    def execute(self, result: FormExtractionResult) -> FormExtractionResult:
        """Execute database mapping"""
        self.start()
        
        try:
            all_fields = result.get_all_fields_with_keys()
            mapped_count = 0
            unmapped_count = 0
            
            # Get mapping patterns
            mapping_patterns = self.pattern_library.mapping_patterns
            
            for field_key, field in all_fields.items():
                field_label_lower = field.label.lower()
                best_match = None
                best_confidence = 0.0
                
                # Try to match against patterns
                for pattern, (table, column, confidence) in mapping_patterns.items():
                    if re.search(pattern, field_label_lower):
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_match = (table, column)
                
                if best_match:
                    table, column = best_match
                    field.mapping_status = MappingStatus.MAPPED
                    field.mapped_to = f"{table}.{column}"
                    field.mapping_confidence = best_confidence
                    
                    # Create mapping record
                    mapping = FieldMapping(
                        pdf_field_key=field_key,
                        pdf_field_label=field.label,
                        database_table=table,
                        database_field=column,
                        confidence=best_confidence
                    )
                    result.mapped_fields[field_key] = mapping
                    mapped_count += 1
                    
                    self.log(f"Mapped '{field.label}' → {table}.{column} (confidence: {best_confidence:.0%})")
                else:
                    field.mapping_status = MappingStatus.UNMAPPED
                    result.unmapped_fields.append(field_key)
                    unmapped_count += 1
            
            # Calculate mapping completeness
            total_fields = len(all_fields)
            result.mapping_completeness = mapped_count / total_fields if total_fields > 0 else 0
            
            self.log(f"Mapped {mapped_count} fields, {unmapped_count} unmapped")
            self.log(f"Mapping completeness: {result.mapping_completeness:.0%}")
            
            self.complete()
            return result
            
        except Exception as e:
            self.log(f"Mapping failed: {str(e)}", "error")
            self.complete(False)
            raise

class MappingValidatorAgent(BaseAgent):
    """Agent for validating field mappings"""
    
    def __init__(self):
        super().__init__(
            "Mapping Validator Agent",
            "Validates and improves field mappings"
        )
    
    def execute(self, result: FormExtractionResult) -> Tuple[bool, float, List[Dict]]:
        """Validate mappings"""
        self.start()
        
        try:
            validation_results = []
            issues = []
            
            # Check required fields
            all_fields = result.get_all_fields_with_keys()
            
            # Validation checks
            checks = [
                {
                    "name": "Required fields mapped",
                    "check": self._check_required_fields,
                    "weight": 2.0
                },
                {
                    "name": "Data type compatibility",
                    "check": self._check_data_types,
                    "weight": 1.5
                },
                {
                    "name": "Mapping confidence",
                    "check": self._check_mapping_confidence,
                    "weight": 1.0
                },
                {
                    "name": "No duplicate mappings",
                    "check": self._check_duplicates,
                    "weight": 1.5
                }
            ]
            
            total_score = 0.0
            total_weight = 0.0
            
            for check in checks:
                passed, score, details = check["check"](result)
                validation_results.append({
                    "check": check["name"],
                    "passed": passed,
                    "score": score,
                    "details": details,
                    "weight": check["weight"]
                })
                
                total_score += score * check["weight"]
                total_weight += check["weight"]
                
                if passed:
                    self.log(f"✓ {check['name']}: {score:.0%}", "success")
                else:
                    self.log(f"✗ {check['name']}: {score:.0%}", "warning")
                    issues.append(details)
            
            overall_score = total_score / total_weight if total_weight > 0 else 0
            is_valid = overall_score >= 0.7
            
            self.log(f"Overall mapping validation score: {overall_score:.0%}")
            self.complete()
            
            return is_valid, overall_score, validation_results
            
        except Exception as e:
            self.log(f"Validation failed: {str(e)}", "error")
            self.complete(False)
            return False, 0.0, []
    
    def _check_required_fields(self, result: FormExtractionResult) -> Tuple[bool, float, str]:
        """Check if required fields are mapped"""
        # Define critical fields that should be mapped
        critical_fields = [
            ('beneficiary', 'firstName'),
            ('beneficiary', 'lastName'),
            ('beneficiary', 'dateOfBirth'),
            ('beneficiary', 'alienNumber')
        ]
        
        mapped_tables = defaultdict(set)
        for mapping in result.mapped_fields.values():
            mapped_tables[mapping.database_table].add(mapping.database_field)
        
        missing = []
        for table, field in critical_fields:
            if field not in mapped_tables.get(table, set()):
                missing.append(f"{table}.{field}")
        
        if not missing:
            return True, 1.0, "All critical fields mapped"
        else:
            score = 1.0 - (len(missing) / len(critical_fields))
            return False, score, f"Missing critical fields: {', '.join(missing)}"
    
    def _check_data_types(self, result: FormExtractionResult) -> Tuple[bool, float, str]:
        """Check data type compatibility"""
        mismatches = []
        total = len(result.mapped_fields)
        correct = 0
        
        for field_key, mapping in result.mapped_fields.items():
            field = result.get_all_fields_with_keys().get(field_key)
            if field:
                # Simple type checking
                if field.field_type == FieldType.DATE and 'date' not in mapping.database_field.lower():
                    mismatches.append(f"{field.label} (DATE) → {mapping.database_field}")
                elif field.field_type == FieldType.NUMBER and mapping.database_field.endswith('Name'):
                    mismatches.append(f"{field.label} (NUMBER) → {mapping.database_field}")
                else:
                    correct += 1
            else:
                correct += 1
        
        score = correct / total if total > 0 else 0
        passed = len(mismatches) == 0
        
        return passed, score, f"Type mismatches: {len(mismatches)}" if mismatches else "All types compatible"
    
    def _check_mapping_confidence(self, result: FormExtractionResult) -> Tuple[bool, float, str]:
        """Check mapping confidence levels"""
        if not result.mapped_fields:
            return False, 0.0, "No mappings to check"
        
        confidences = [m.confidence for m in result.mapped_fields.values()]
        avg_confidence = sum(confidences) / len(confidences)
        low_confidence = [m for m in result.mapped_fields.values() if m.confidence < 0.7]
        
        if avg_confidence >= 0.8 and not low_confidence:
            return True, 1.0, f"Average confidence: {avg_confidence:.0%}"
        else:
            return False, avg_confidence, f"Low confidence mappings: {len(low_confidence)}"
    
    def _check_duplicates(self, result: FormExtractionResult) -> Tuple[bool, float, str]:
        """Check for duplicate mappings"""
        mapping_targets = defaultdict(list)
        
        for field_key, mapping in result.mapped_fields.items():
            target = f"{mapping.database_table}.{mapping.database_field}"
            mapping_targets[target].append(field_key)
        
        duplicates = {k: v for k, v in mapping_targets.items() if len(v) > 1}
        
        if not duplicates:
            return True, 1.0, "No duplicate mappings"
        else:
            return False, 0.5, f"Duplicate mappings found: {len(duplicates)}"

class ManualMappingAgent(BaseAgent):
    """Agent for handling manual field additions and mappings"""
    
    def __init__(self):
        super().__init__(
            "Manual Mapping Agent",
            "Handles manual field additions and user-defined mappings"
        )
    
    def execute(self, manual_fields: List[Dict], result: FormExtractionResult) -> FormExtractionResult:
        """Process manual field additions"""
        self.start()
        
        try:
            added_count = 0
            
            for manual_field in manual_fields:
                # Create new field node
                field_key = f"MANUAL_{len(result.get_all_fields_with_keys()) + added_count}"
                
                field_node = FieldNode(
                    item_number=field_key,
                    label=manual_field['label'],
                    value=manual_field['value'],
                    field_type=FieldType.TEXT,
                    page=0,
                    confidence=ExtractionConfidence.HIGH,
                    extraction_method="manual",
                    mapping_status=MappingStatus.MANUAL,
                    mapped_to=manual_field.get('mapped_to')
                )
                
                # Add to appropriate part (create manual part if needed)
                if 99 not in result.parts:
                    result.parts[99] = PartStructure(
                        part_number=99,
                        part_name="Manual Entries",
                        part_title="Manually Added Fields"
                    )
                
                result.parts[99].root_fields.append(field_node)
                
                # Create mapping if specified
                if manual_field.get('mapped_to'):
                    table, field = manual_field['mapped_to'].split('.')
                    mapping = FieldMapping(
                        pdf_field_key=field_key,
                        pdf_field_label=manual_field['label'],
                        database_table=table,
                        database_field=field,
                        confidence=1.0
                    )
                    result.mapped_fields[field_key] = mapping
                
                added_count += 1
                self.log(f"Added manual field: {manual_field['label']}")
            
            self.log(f"Added {added_count} manual fields", "success")
            self.complete()
            return result
            
        except Exception as e:
            self.log(f"Manual mapping failed: {str(e)}", "error")
            self.complete(False)
            raise

class TypeScriptGeneratorAgent(BaseAgent):
    """Agent for generating TypeScript interfaces"""
    
    def __init__(self):
        super().__init__(
            "TypeScript Generator Agent",
            "Generates TypeScript interfaces from mapped fields"
        )
    
    def execute(self, result: FormExtractionResult) -> str:
        """Generate TypeScript interfaces"""
        self.start()
        
        try:
            ts_code = f"// Generated TypeScript interfaces for {result.form_number}\n"
            ts_code += f"// Generated on: {datetime.now().isoformat()}\n\n"
            
            # Group mappings by table
            tables = defaultdict(list)
            for mapping in result.mapped_fields.values():
                tables[mapping.database_table].append(mapping)
            
            # Generate interfaces
            for table, mappings in tables.items():
                interface_name = self._to_pascal_case(table)
                ts_code += f"export interface {interface_name} {{\n"
                
                # Get unique fields
                fields = {}
                for mapping in mappings:
                    if mapping.database_field not in fields:
                        field_type = self._get_typescript_type(mapping.database_field)
                        fields[mapping.database_field] = field_type
                
                # Write fields
                for field_name, field_type in sorted(fields.items()):
                    ts_code += f"  {field_name}: {field_type};\n"
                
                ts_code += "}\n\n"
            
            # Generate main form interface
            form_interface = self._to_pascal_case(result.form_number.replace('-', ''))
            ts_code += f"export interface {form_interface}FormData {{\n"
            for table in tables.keys():
                interface_name = self._to_pascal_case(table)
                ts_code += f"  {table}: {interface_name};\n"
            ts_code += "}\n\n"
            
            # Generate validation schema
            ts_code += f"// Validation schema\n"
            ts_code += f"export const {form_interface}ValidationSchema = {{\n"
            for table in tables.keys():
                ts_code += f"  {table}: {{\n"
                ts_code += f"    required: ['firstName', 'lastName', 'dateOfBirth'],\n"
                ts_code += f"  }},\n"
            ts_code += "};\n"
            
            self.log(f"Generated TypeScript for {len(tables)} tables", "success")
            self.complete()
            return ts_code
            
        except Exception as e:
            self.log(f"TypeScript generation failed: {str(e)}", "error")
            self.complete(False)
            raise
    
    def _to_pascal_case(self, text: str) -> str:
        """Convert to PascalCase"""
        return ''.join(word.capitalize() for word in text.split('_'))
    
    def _get_typescript_type(self, field_name: str) -> str:
        """Determine TypeScript type from field name"""
        if 'date' in field_name.lower():
            return 'string | Date'
        elif 'number' in field_name.lower() or field_name.endswith('Count'):
            return 'number'
        elif field_name.endswith('Flag') or field_name.startswith('is'):
            return 'boolean'
        else:
            return 'string'

class JSONExportAgent(BaseAgent):
    """Agent for exporting mapped data as JSON"""
    
    def __init__(self):
        super().__init__(
            "JSON Export Agent",
            "Exports mapped data in various JSON formats"
        )
    
    def execute(self, result: FormExtractionResult) -> Dict[str, Any]:
        """Generate JSON exports"""
        self.start()
        
        try:
            all_fields = result.get_all_fields_with_keys()
            
            # Generate mapped data JSON
            mapped_data = defaultdict(dict)
            for field_key, mapping in result.mapped_fields.items():
                if field_key in all_fields:
                    value = all_fields[field_key].value
                    mapped_data[mapping.database_table][mapping.database_field] = value
            
            # Generate unmapped fields JSON
            unmapped_data = {}
            for field_key in result.unmapped_fields:
                if field_key in all_fields:
                    field = all_fields[field_key]
                    unmapped_data[field_key] = {
                        "label": field.label,
                        "value": field.value,
                        "type": field.field_type.value,
                        "page": field.page,
                        "confidence": field.confidence.value
                    }
            
            # Generate complete export
            export = {
                "metadata": {
                    "form_number": result.form_number,
                    "form_title": result.form_title,
                    "extraction_date": datetime.now().isoformat(),
                    "total_fields": result.total_fields,
                    "mapped_count": len(result.mapped_fields),
                    "unmapped_count": len(result.unmapped_fields),
                    "mapping_completeness": result.mapping_completeness
                },
                "mapped_data": dict(mapped_data),
                "unmapped_fields": unmapped_data
            }
            
            self.log(f"Generated JSON export with {len(mapped_data)} tables", "success")
            self.complete()
            return export
            
        except Exception as e:
            self.log(f"JSON export failed: {str(e)}", "error")
            self.complete(False)
            raise

# ===== ENHANCED MASTER COORDINATOR =====
class EnhancedMasterCoordinator(BaseAgent):
    """Enhanced coordinator that manages both extraction and mapping agents"""
    
    def __init__(self, max_iterations: int = 3):
        super().__init__(
            "Enhanced Master Coordinator",
            "Orchestrates extraction and database mapping"
        )
        self.max_iterations = max_iterations
        
        # Extraction agents
        self.extraction_agents = {
            'extractor': AdaptivePatternExtractor(),
            'assigner': SmartKeyAssignment(),
            'validator': QuestionnaireValidator(),
            'formatter': OutputFormatter()
        }
        
        # Mapping agents
        self.mapping_agents = {
            'mapper': DatabaseMappingAgent(),
            'mapping_validator': MappingValidatorAgent(),
            'manual_mapper': ManualMappingAgent(),
            'ts_generator': TypeScriptGeneratorAgent(),
            'json_exporter': JSONExportAgent()
        }
        
        self.pattern_library = PatternLibrary()
    
    def execute(self, pdf_file, manual_fields: List[Dict] = None) -> Dict[str, Any]:
        """Execute complete extraction and mapping pipeline"""
        self.start()
        
        try:
            # Phase 1: Extraction
            self.log("=== PHASE 1: PDF EXTRACTION ===")
            extraction_result = self._run_extraction_phase(pdf_file)
            
            if not extraction_result:
                self.log("Extraction phase failed", "error")
                self.complete(False)
                return None
            
            # Phase 2: Database Mapping
            self.log("\n=== PHASE 2: DATABASE MAPPING ===")
            mapping_result = self._run_mapping_phase(extraction_result, manual_fields)
            
            # Phase 3: Validation
            self.log("\n=== PHASE 3: MAPPING VALIDATION ===")
            validation_result = self._run_validation_phase(mapping_result)
            
            # Phase 4: Export Generation
            self.log("\n=== PHASE 4: EXPORT GENERATION ===")
            export_result = self._run_export_phase(mapping_result)
            
            # Combine all results
            final_output = {
                'extraction': extraction_result.to_output_format(),
                'mapping': {
                    'mapped_fields': {k: asdict(v) for k, v in mapping_result.mapped_fields.items()},
                    'unmapped_fields': mapping_result.unmapped_fields,
                    'completeness': mapping_result.mapping_completeness
                },
                'validation': validation_result,
                'exports': export_result,
                '_metadata': {
                    'form_number': extraction_result.form_number,
                    'form_title': extraction_result.form_title,
                    'total_fields': extraction_result.total_fields,
                    'extraction_score': extraction_result.validation_score,
                    'mapping_completeness': mapping_result.mapping_completeness,
                    'timestamp': datetime.now().isoformat()
                }
            }
            
            self.log("✅ Complete pipeline executed successfully!", "success")
            self.complete()
            return final_output
            
        except Exception as e:
            self.log(f"Pipeline failed: {str(e)}", "error", traceback.format_exc())
            self.complete(False)
            return None
    
    def _run_extraction_phase(self, pdf_file) -> Optional[FormExtractionResult]:
        """Run extraction phase"""
        best_result = None
        best_score = 0.0
        
        for iteration in range(self.max_iterations):
            self.log(f"Extraction iteration {iteration + 1}/{self.max_iterations}")
            
            # Extract
            if iteration == 0:
                result = self.extraction_agents['extractor'].execute(pdf_file)
            else:
                result = self._refine_extraction(pdf_file, result, validation_results)
            
            if not result:
                break
            
            # Assign keys
            result = self.extraction_agents['assigner'].execute(result)
            
            # Validate
            schema = self.pattern_library.form_schemas.get(result.form_number)
            is_valid, score, validation_results = self.extraction_agents['validator'].execute(result, schema)
            
            if score > best_score:
                best_score = score
                best_result = copy.deepcopy(result)
            
            if is_valid and score >= 0.85:
                self.log(f"Extraction successful with score {score:.0%}", "success")
                break
        
        return best_result
    
    def _run_mapping_phase(self, extraction_result: FormExtractionResult, 
                          manual_fields: Optional[List[Dict]]) -> FormExtractionResult:
        """Run mapping phase"""
        # Auto-map fields
        result = self.mapping_agents['mapper'].execute(extraction_result)
        
        # Add manual fields if provided
        if manual_fields:
            result = self.mapping_agents['manual_mapper'].execute(manual_fields, result)
        
        return result
    
    def _run_validation_phase(self, mapping_result: FormExtractionResult) -> Dict:
        """Run validation phase"""
        is_valid, score, details = self.mapping_agents['mapping_validator'].execute(mapping_result)
        
        return {
            'is_valid': is_valid,
            'score': score,
            'details': details
        }
    
    def _run_export_phase(self, mapping_result: FormExtractionResult) -> Dict:
        """Run export phase"""
        # Generate TypeScript
        typescript = self.mapping_agents['ts_generator'].execute(mapping_result)
        
        # Generate JSON
        json_export = self.mapping_agents['json_exporter'].execute(mapping_result)
        
        return {
            'typescript': typescript,
            'json': json_export
        }
    
    def _refine_extraction(self, pdf_file, previous_result: FormExtractionResult,
                         validation_results: List[Dict]) -> FormExtractionResult:
        """Refine extraction based on validation feedback"""
        # Analyze issues and re-extract
        issues = [r for r in validation_results if not r["passed"]]
        self.log(f"Refining based on {len(issues)} validation issues")
        
        return self.extraction_agents['extractor'].execute(pdf_file)

# ===== UI COMPONENTS =====
def display_agent_activity():
    """Display agent activity log"""
    if 'agent_container' not in st.session_state:
        st.session_state.agent_container = st.container()
    return st.session_state.agent_container

def display_mapping_results(result: Dict):
    """Display mapping results"""
    if not result:
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### ✅ Mapped Fields")
        mapped = result.get('mapping', {}).get('mapped_fields', {})
        for field_key, mapping in mapped.items():
            st.markdown(
                f'<div class="field-card mapped-field">'
                f'<strong>{mapping["pdf_field_label"]}</strong><br>'
                f'PDF Key: {mapping["pdf_field_key"]}<br>'
                f'➡️ {mapping["database_table"]}.{mapping["database_field"]}<br>'
                f'Confidence: {mapping["confidence"]:.0%}'
                f'</div>',
                unsafe_allow_html=True
            )
    
    with col2:
        st.markdown("### ❓ Unmapped Fields")
        unmapped = result.get('mapping', {}).get('unmapped_fields', [])
        extraction_data = result.get('extraction', {})
        
        for field_key in unmapped:
            label = extraction_data.get(f"{field_key}_title", field_key)
            value = extraction_data.get(field_key, "")
            st.markdown(
                f'<div class="field-card unmapped-field">'
                f'<strong>{label}</strong><br>'
                f'Key: {field_key}<br>'
                f'Value: {value}'
                f'</div>',
                unsafe_allow_html=True
            )

# ===== MAIN APPLICATION =====
def main():
    st.markdown(
        '<div class="main-header">'
        '<h1>🤖 Advanced Multi-Agent USCIS Form Reader</h1>'
        '<p>PDF Extraction → Database Mapping → TypeScript/JSON Export</p>'
        '</div>', 
        unsafe_allow_html=True
    )
    
    # Initialize session state
    if 'pipeline_result' not in st.session_state:
        st.session_state.pipeline_result = None
    if 'manual_fields' not in st.session_state:
        st.session_state.manual_fields = []
    
    # Sidebar
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        max_iterations = st.slider("Max Extraction Iterations", 1, 5, 3)
        show_agent_logs = st.checkbox("Show Agent Activity", value=True)
        
        st.markdown("---")
        st.markdown("## 🤖 Active Agents")
        
        st.markdown("### Extraction Agents")
        st.markdown("- 🔍 Adaptive Pattern Extractor")
        st.markdown("- 🏷️ Smart Key Assignment")
        st.markdown("- ✅ Questionnaire Validator")
        st.markdown("- 📄 Output Formatter")
        
        st.markdown("### Mapping Agents")
        st.markdown("- 🔗 Database Mapping Agent")
        st.markdown("- ✓ Mapping Validator")
        st.markdown("- ✏️ Manual Mapping Agent")
        st.markdown("- 📘 TypeScript Generator")
        st.markdown("- 📦 JSON Export Agent")
        
        st.markdown("---")
        st.markdown("## 📊 System Status")
        
        if PYMUPDF_AVAILABLE:
            st.success("✅ PyMuPDF Ready")
        else:
            st.error("❌ PyMuPDF Not Installed")
            st.code("pip install PyMuPDF")
    
    # Main content
    tabs = st.tabs([
        "📄 Upload & Process",
        "🔗 Mapping Results",
        "✏️ Manual Fields",
        "💾 Export Results"
    ])
    
    # Tab 1: Upload & Process
    with tabs[0]:
        st.markdown("### 📄 Upload USCIS Form")
        
        uploaded_file = st.file_uploader(
            "Choose a PDF form",
            type=['pdf'],
            help="Supported forms: I-539, I-129, G-28, I-90, I-485, I-765, N-400"
        )
        
        if uploaded_file:
            st.success(f"✅ Uploaded: {uploaded_file.name}")
            
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                if st.button("🚀 Run Complete Pipeline", type="primary", use_container_width=True):
                    # Create agent activity container
                    if show_agent_logs:
                        st.markdown("### 🤖 Agent Activity")
                        agent_container = st.container()
                        st.session_state.agent_container = agent_container
                    
                    with st.spinner("Running multi-agent pipeline..."):
                        # Run enhanced coordinator
                        coordinator = EnhancedMasterCoordinator(max_iterations=max_iterations)
                        result = coordinator.execute(uploaded_file, st.session_state.manual_fields)
                        
                        if result:
                            st.session_state.pipeline_result = result
                            st.success("✅ Pipeline completed successfully!")
                            
                            # Show summary metrics
                            metadata = result.get('_metadata', {})
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.metric("Form", metadata.get('form_number', 'Unknown'))
                            with col2:
                                st.metric("Total Fields", metadata.get('total_fields', 0))
                            with col3:
                                st.metric("Extraction Score", f"{metadata.get('extraction_score', 0):.0%}")
                            with col4:
                                st.metric("Mapping Complete", f"{metadata.get('mapping_completeness', 0):.0%}")
                        else:
                            st.error("❌ Pipeline failed")
            
            with col2:
                if st.button("🔄 Reset", use_container_width=True):
                    st.session_state.pipeline_result = None
                    st.session_state.manual_fields = []
                    st.rerun()
    
    # Tab 2: Mapping Results
    with tabs[1]:
        st.markdown("### 🔗 Field Mapping Results")
        
        if st.session_state.pipeline_result:
            display_mapping_results(st.session_state.pipeline_result)
            
            # Mapping statistics
            st.markdown("### 📊 Mapping Statistics")
            mapping_data = st.session_state.pipeline_result.get('mapping', {})
            validation_data = st.session_state.pipeline_result.get('validation', {})
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Mapped Fields", len(mapping_data.get('mapped_fields', {})))
            with col2:
                st.metric("Unmapped Fields", len(mapping_data.get('unmapped_fields', [])))
            with col3:
                st.metric("Validation Score", f"{validation_data.get('score', 0):.0%}")
            
            # Validation details
            if validation_data.get('details'):
                with st.expander("📋 Validation Details"):
                    for detail in validation_data['details']:
                        icon = "✅" if detail['passed'] else "❌"
                        st.markdown(f"{icon} **{detail['check']}**: {detail['score']:.0%}")
                        st.caption(detail['details'])
        else:
            st.info("No results yet. Please process a form first.")
    
    # Tab 3: Manual Fields
    with tabs[2]:
        st.markdown("### ✏️ Add Manual Fields")
        
        with st.form("manual_field_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                field_label = st.text_input("Field Label")
                field_value = st.text_input("Field Value")
            
            with col2:
                # Database schema selector
                db_options = ["-- Select Database Field --"]
                schema = DatabaseSchema()
                for table, fields in schema.tables.items():
                    for field_name in fields:
                        db_options.append(f"{table}.{field_name}")
                
                mapped_to = st.selectbox("Map to Database Field", db_options)
            
            if st.form_submit_button("➕ Add Manual Field"):
                if field_label and field_value:
                    manual_field = {
                        'label': field_label,
                        'value': field_value,
                        'mapped_to': mapped_to if mapped_to != db_options[0] else None
                    }
                    st.session_state.manual_fields.append(manual_field)
                    st.success(f"Added manual field: {field_label}")
                    st.rerun()
        
        # Display manual fields
        if st.session_state.manual_fields:
            st.markdown("#### 📝 Current Manual Fields")
            for idx, field in enumerate(st.session_state.manual_fields):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.info(f"**{field['label']}**: {field['value']}")
                    if field.get('mapped_to'):
                        st.caption(f"Mapped to: {field['mapped_to']}")
                with col2:
                    if st.button("❌", key=f"del_{idx}"):
                        st.session_state.manual_fields.pop(idx)
                        st.rerun()
    
    # Tab 4: Export
    with tabs[3]:
        st.markdown("### 💾 Export Results")
        
        if st.session_state.pipeline_result:
            exports = st.session_state.pipeline_result.get('exports', {})
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("#### 📘 TypeScript Interface")
                if exports.get('typescript'):
                    st.download_button(
                        "⬇️ Download TypeScript",
                        exports['typescript'],
                        "form_interfaces.ts",
                        mime="text/plain",
                        use_container_width=True
                    )
            
            with col2:
                st.markdown("#### 📦 Mapped Data JSON")
                if exports.get('json'):
                    json_str = json.dumps(exports['json']['mapped_data'], indent=2)
                    st.download_button(
                        "⬇️ Download Mapped JSON",
                        json_str,
                        "mapped_data.json",
                        mime="application/json",
                        use_container_width=True
                    )
            
            with col3:
                st.markdown("#### ❓ Unmapped Fields")
                if exports.get('json', {}).get('unmapped_fields'):
                    json_str = json.dumps(exports['json']['unmapped_fields'], indent=2)
                    st.download_button(
                        "⬇️ Download Unmapped JSON",
                        json_str,
                        "unmapped_fields.json",
                        mime="application/json",
                        use_container_width=True
                    )
            
            # Preview sections
            st.markdown("### 👁️ Export Preview")
            
            preview_tabs = st.tabs(["TypeScript", "Mapped JSON", "Complete Export"])
            
            with preview_tabs[0]:
                if exports.get('typescript'):
                    st.code(exports['typescript'], language='typescript')
            
            with preview_tabs[1]:
                if exports.get('json'):
                    st.json(exports['json']['mapped_data'])
            
            with preview_tabs[2]:
                st.json(st.session_state.pipeline_result)
        else:
            st.info("No results to export. Please process a form first.")

if __name__ == "__main__":
    # Check dependencies
    if not PYMUPDF_AVAILABLE:
        st.error("❌ PyMuPDF is required but not installed!")
        st.code("pip install PyMuPDF")
        st.info("After installing, refresh this page.")
        st.stop()
    
    main()
