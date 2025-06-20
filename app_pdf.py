#!/usr/bin/env python3
"""
Test script for USCIS Form Processor
Demonstrates how to use the form processor programmatically
"""

import json
import sys
from pathlib import Path

# Import the processor class from the main application
from uscis_form_generator import USCISFormProcessor, FormField, FormConfig
from uscis_form_generator import generate_typescript_config, generate_questionnaire_json, update_pdf_mapper

def test_form_processor():
    """Test the form processor with sample data"""
    
    # Initialize processor
    processor = USCISFormProcessor()
    
    # Test field categorization
    test_fields = [
        "petitioner_last_name",
        "beneficiary_first_name", 
        "attorney_phone",
        "case_type",
        "part_1_question_a",
        "signature_date"
    ]
    
    print("Testing field categorization:")
    for field in test_fields:
        category = processor.categorize_field(field)
        field_type = processor.determine_field_type(field)
        mapping = processor.generate_mapping_path(field, category)
        
        print(f"  {field}:")
        print(f"    Category: {category}")
        print(f"    Type: {field_type}")
        print(f"    Mapping: {mapping}")
        print()

def create_sample_form_config():
    """Create a sample form configuration for testing"""
    
    # Create sample fields
    fields = [
        FormField(
            name="petitioner_last_name",
            field_type="text",
            category="customer",
            mapping_path="customer.signatory_last_name",
            required=True
        ),
        FormField(
            name="petitioner_first_name", 
            field_type="text",
            category="customer",
            mapping_path="customer.signatory_first_name",
            required=True
        ),
        FormField(
            name="beneficiary_last_name",
            field_type="text",
            category="beneficiary", 
            mapping_path="beneficary.Beneficiary.beneficiaryLastName",
            required=True
        ),
        FormField(
            name="attorney_phone",
            field_type="text",
            category="attorney",
            mapping_path="attorney.attorneyInfo.workPhone",
            required=False
        ),
        FormField(
            name="relationship_type",
            field_type="dropdown",
            category="questionnaire",
            mapping_path="relationship_type:DropdownBox",
            required=True
        )
    ]
    
    # Create form configuration
    form_config = FormConfig(
        form_name="I130_TEST",
        form_type="I-130",
        pdf_name="I-130 Test Form",
        fields=fields,
        sections=["customer", "beneficiary", "attorney", "questionnaire"]
    )
    
    return form_config

def test_config_generation():
    """Test configuration file generation"""
    
    print("Creating sample form configuration...")
    form_config = create_sample_form_config()
    
    print(f"Form: {form_config.form_name}")
    print(f"Fields: {len(form_config.fields)}")
    print(f"Sections: {form_config.sections}")
    print()
    
    # Generate TypeScript configuration
    print("Generating TypeScript configuration...")
    ts_config = generate_typescript_config(form_config)
    
    # Save to file
    ts_file = Path(f"{form_config.form_name}.ts")
    with open(ts_file, 'w') as f:
        f.write(ts_config)
    print(f"TypeScript config saved to: {ts_file}")
    print()
    
    # Generate questionnaire JSON
    print("Generating questionnaire JSON...")
    questionnaire_json = generate_questionnaire_json(form_config)
    
    # Save to file
    json_file = Path(f"{form_config.form_name}-form.json")
    with open(json_file, 'w') as f:
        json.dump(questionnaire_json, f, indent=2)
    print(f"Questionnaire JSON saved to: {json_file}")
    print()
    
    # Generate PDF mapper
    print("Generating PDF mapper...")
    mapper_config = update_pdf_mapper(form_config.form_name, form_config.fields)
    
    # Save to file
    mapper_file = Path(f"{form_config.form_name}-mapper.ts")
    with open(mapper_file, 'w') as f:
        f.write(mapper_config)
    print(f"PDF mapper saved to: {mapper_file}")
    print()
    
    return {
        'typescript': ts_config,
        'questionnaire': questionnaire_json,
        'mapper': mapper_config
    }

def validate_generated_configs(configs):
    """Validate the generated configurations"""
    
    print("Validating generated configurations...")
    
    # Check TypeScript config
    ts_config = configs['typescript']
    if 'customerData' in ts_config and 'beneficiaryData' in ts_config:
        print("✓ TypeScript config contains required sections")
    else:
        print("✗ TypeScript config missing required sections")
    
    # Check questionnaire JSON
    questionnaire = configs['questionnaire']
    if 'controls' in questionnaire and len(questionnaire['controls']) > 0:
        print("✓ Questionnaire JSON contains controls")
    else:
        print("✗ Questionnaire JSON missing controls")
    
    # Check mapper config
    mapper = configs['mapper']
    if 'Name' in mapper and 'Value' in mapper and 'Type' in mapper:
        print("✓ PDF mapper contains required fields")
    else:
        print("✗ PDF mapper missing required fields")
    
    print()

def process_pdf_file(pdf_path):
    """Process a real PDF file if provided"""
    
    if not Path(pdf_path).exists():
        print(f"PDF file not found: {pdf_path}")
        return
    
    print(f"Processing PDF file: {pdf_path}")
    
    processor = USCISFormProcessor()
    
    try:
        with open(pdf_path, 'rb') as pdf_file:
            fields = processor.extract_pdf_fields(pdf_file)
            
        if fields:
            print(f"Extracted {len(fields)} fields:")
            for i, field in enumerate(fields[:10], 1):  # Show first 10 fields
                print(f"  {i}. {field}")
            
            if len(fields) > 10:
                print(f"  ... and {len(fields) - 10} more fields")
        else:
            print("No fields found in PDF")
            
    except Exception as e:
        print(f"Error processing PDF: {e}")

def main():
    """Main test function"""
    
    print("USCIS Form Processor Test Script")
    print("=" * 40)
    print()
    
    # Test basic functionality
    test_form_processor()
    
    # Test configuration generation
    configs = test_config_generation()
    
    # Validate generated configurations
    validate_generated_configs(configs)
    
    # Process PDF file if provided as command line argument
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        process_pdf_file(pdf_path)
    
    print("Test completed!")

if __name__ == "__main__":
    main()
