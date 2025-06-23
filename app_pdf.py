def extract_pdf_fields(self, pdf_file, form_type: str) -> List[PDFField]:
    """Extract all fields from any USCIS PDF form with accurate part detection"""
    fields = []
    
    try:
        pdf_bytes = pdf_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # First, let's understand the form structure by looking at all field names
        all_field_names = []
        field_index = 0
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            for widget in page.widgets():
                if widget.field_name:
                    all_field_names.append(widget.field_name)
                    field_index += 1
                    
                    # Extract field information
                    field_type = self._get_field_type(widget)
                    
                    # Extract part directly from field name
                    part = self._extract_part_from_field_name_improved(widget.field_name, page_num)
                    
                    # Extract other metadata
                    item = self._extract_item(widget.field_name)
                    description = self._generate_description(widget.field_name, widget.field_display)
                    
                    # Create field object
                    pdf_field = PDFField(
                        index=field_index,
                        raw_name=widget.field_name,
                        field_type=field_type,
                        value=widget.field_value or '',
                        page=page_num + 1,
                        part=part,
                        item=item,
                        description=description
                    )
                    
                    # Get mapping suggestions
                    suggestions = self._get_mapping_suggestions(pdf_field)
                    if suggestions:
                        best_suggestion = suggestions[0]
                        pdf_field.db_mapping = best_suggestion.db_path
                        pdf_field.confidence_score = best_suggestion.confidence
                        pdf_field.mapping_type = best_suggestion.field_type
                    else:
                        # Automatically mark unmapped fields as questionnaire
                        pdf_field.is_questionnaire = True
                    
                    fields.append(pdf_field)
        
        doc.close()
        
        # Debug: Print field name patterns to understand structure
        print(f"\nForm: {form_type}")
        print(f"Total fields: {len(fields)}")
        print("\nSample field names (first 10):")
        for i, name in enumerate(all_field_names[:10]):
            print(f"  {i+1}: {name}")
        
        # Print part distribution
        part_counts = {}
        for field in fields:
            part_counts[field.part] = part_counts.get(field.part, 0) + 1
        print("\nPart distribution:")
        for part, count in sorted(part_counts.items()):
            print(f"  {part}: {count} fields")
        
    except Exception as e:
        st.error(f"Error extracting PDF: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return []
    
    return fields

def _extract_part_from_field_name_improved(self, field_name: str, page_num: int) -> str:
    """Extract part from field name with improved pattern matching"""
    
    # Debug: uncomment to see field names
    # print(f"Parsing field: {field_name}")
    
    # Common USCIS form field name patterns
    # Many forms use patterns like:
    # - form1[0].#subform[0].Part1_Line1a_FamilyName[0]
    # - Part1_Item1_Name
    # - Pt1Line1aFamilyName
    # - P1_1a_FamilyName
    
    # Clean up the field name first
    clean_name = field_name
    
    # Remove form array indices
    clean_name = re.sub(r'\[\d+\]', '', clean_name)
    
    # Look for explicit part indicators
    part_patterns = [
        # Standard Part patterns
        (r'Part\s*(\d+)', lambda m: f"Part {m.group(1)}"),
        (r'Part(\d+)', lambda m: f"Part {m.group(1)}"),
        (r'Pt\s*(\d+)', lambda m: f"Part {m.group(1)}"),
        (r'Pt(\d+)', lambda m: f"Part {m.group(1)}"),
        (r'P(\d+)[_\.\-]', lambda m: f"Part {m.group(1)}"),
        
        # Subform patterns that might indicate parts
        (r'#subform\[(\d+)\]', lambda m: f"Part {int(m.group(1)) + 1}" if int(m.group(1)) > 0 else "Part 1"),
        
        # Special patterns for attorney section (usually at beginning)
        (r'(attorney|g28|g-28|representative|preparer)', lambda m: "Part 0 - Attorney/Representative"),
        
        # Section patterns
        (r'Section\s*([A-Z])', lambda m: f"Section {m.group(1)}"),
        (r'Section\s*(\d+)', lambda m: f"Section {m.group(1)}"),
    ]
    
    for pattern, formatter in part_patterns:
        match = re.search(pattern, clean_name, re.IGNORECASE)
        if match:
            part = formatter(match)
            # Special handling for Part 0
            if part == "Part 0":
                return "Part 0 - Attorney/Representative"
            return part
    
    # Check if this is the first page and contains attorney-related fields
    if page_num == 0:
        attorney_keywords = [
            'attorney', 'lawyer', 'representative', 'bar', 'law',
            'firm', 'fein', 'bia', 'accredited', 'g-28', 'g28',
            'appearance', 'counsel', 'legal'
        ]
        
        field_lower = field_name.lower()
        if any(keyword in field_lower for keyword in attorney_keywords):
            return "Part 0 - Attorney/Representative"
    
    # If no part found, check page-based heuristics
    # Many forms have attorney section on page 1
    if page_num == 0 and not any(p in clean_name.lower() for p in ['part1', 'part 1', 'pt1']):
        # Check if this looks like an attorney field
        common_attorney_fields = [
            'name', 'address', 'city', 'state', 'zip', 'phone',
            'email', 'signature', 'bar', 'law', 'firm'
        ]
        if any(field in field_name.lower() for field in common_attorney_fields):
            # But make sure it's not explicitly Part 1
            if not re.search(r'(part|pt)\s*1', field_name, re.IGNORECASE):
                return "Part 0 - Attorney/Representative"
    
    # Default to page number if no part found
    return f"Page {page_num + 1}"

def _post_process_parts_improved(self, fields: List[PDFField]):
    """Post-process to ensure correct part assignment with better logic"""
    
    # First, let's analyze the field patterns to understand the form structure
    field_patterns = {}
    for field in fields:
        # Extract base pattern from field name
        base_pattern = re.sub(r'\[\d+\]', '', field.raw_name)
        base_pattern = re.sub(r'#subform', 'subform', base_pattern)
        
        if base_pattern not in field_patterns:
            field_patterns[base_pattern] = []
        field_patterns[base_pattern].append(field)
    
    # Look for clear part indicators in the patterns
    part_assignments = {}
    for pattern, pattern_fields in field_patterns.items():
        # Check if pattern contains part information
        part_match = re.search(r'(Part|Pt)(\d+)', pattern, re.IGNORECASE)
        if part_match:
            part_num = part_match.group(2)
            part_name = f"Part {part_num}"
            if part_num == "0":
                part_name = "Part 0 - Attorney/Representative"
            
            # Assign this part to all fields with this pattern
            for field in pattern_fields:
                part_assignments[field.index] = part_name
    
    # Apply the assignments
    for field in fields:
        if field.index in part_assignments:
            field.part = part_assignments[field.index]
    
    # Special handling for forms that don't have clear part indicators
    # If we don't have many part assignments, use page-based heuristics
    assigned_count = sum(1 for f in fields if not f.part.startswith("Page"))
    if assigned_count < len(fields) * 0.5:  # Less than 50% have parts
        # Use position-based heuristics for common form structures
        self._apply_position_based_parts(fields)
    
    return fields

def _apply_position_based_parts(self, fields: List[PDFField]):
    """Apply position-based part assignment for forms without clear part markers"""
    
    # Group fields by page
    page_fields = {}
    for field in fields:
        if field.page not in page_fields:
            page_fields[field.page] = []
        page_fields[field.page].append(field)
    
    # Common USCIS form structure:
    # Page 1: Often attorney/preparer info at top, then Part 1
    # Page 2+: Usually continuation of parts
    
    # Check first page for attorney section
    if 1 in page_fields:
        first_page = page_fields[1]
        
        # Look for attorney section indicators in first few fields
        attorney_section_end = None
        for i, field in enumerate(first_page[:20]):  # Check first 20 fields
            field_lower = field.description.lower() + field.raw_name.lower()
            
            # Check if this is clearly Part 1
            if re.search(r'part\s*1|pt\s*1', field_lower):
                attorney_section_end = i
                break
            
            # Check for petitioner/applicant info (usually Part 1)
            if any(term in field_lower for term in ['petitioner', 'applicant', 'employer']):
                attorney_section_end = i
                break
        
        # Assign attorney section to fields before Part 1
        if attorney_section_end is not None and attorney_section_end > 0:
            for i in range(attorney_section_end):
                if page_fields[1][i].part.startswith("Page"):
                    page_fields[1][i].part = "Part 0 - Attorney/Representative"
    
    # For remaining unassigned fields, try to infer from content
    current_part = "Part 1"
    for page_num in sorted(page_fields.keys()):
        for field in page_fields[page_num]:
            if field.part.startswith("Page"):
                # Try to detect part transitions based on content
                field_text = field.description.lower()
                
                if any(term in field_text for term in ['beneficiary', 'worker', 'employee information']):
                    current_part = "Part 2"
                elif any(term in field_text for term in ['dependent', 'family member']):
                    current_part = "Part 3"
                elif any(term in field_text for term in ['additional information', 'supplemental']):
                    current_part = "Part 4"
                
                field.part = current_part
