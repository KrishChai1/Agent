# Add this to your upload tab to debug extraction issues

def render_upload_tab_with_debug():
    """Upload and extraction tab with debugging"""
    st.markdown("### Upload USCIS Form")
    
    # Debug mode toggle
    debug_mode = st.checkbox("🔧 Enable Debug Mode", value=False)
    
    uploaded_file = st.file_uploader(
        "Choose PDF file",
        type=['pdf'],
        help="Upload any USCIS form"
    )
    
    if uploaded_file:
        st.info(f"📄 {uploaded_file.name}")
        
        if st.button("🚀 Extract Form", type="primary"):
            try:
                # Step 1: Extract PDF text
                with st.spinner("Step 1: Reading PDF..."):
                    text, page_count = extract_pdf_text(uploaded_file)
                    
                    if debug_mode:
                        st.success(f"✓ PDF read successfully: {page_count} pages, {len(text)} characters")
                        with st.expander("View first 1000 characters"):
                            st.text(text[:1000])
                
                if not text:
                    st.error("❌ Could not extract text from PDF")
                    return
                
                # Step 2: Extract form structure
                with st.spinner("Step 2: Extracting structure..."):
                    # Simple extraction without AI
                    form_number = "Unknown"
                    form_match = re.search(r'Form\s+([I]-\d+[A-Z]?)', text[:3000], re.IGNORECASE)
                    if form_match:
                        form_number = form_match.group(1)
                    
                    if debug_mode:
                        st.success(f"✓ Form identified: {form_number}")
                
                # Step 3: Extract parts
                with st.spinner("Step 3: Finding parts..."):
                    parts = []
                    part_pattern = r'Part\s+(\d+)[.\s\-–]*([^\n]{3,100})'
                    matches = re.finditer(part_pattern, text, re.IGNORECASE)
                    
                    for match in matches:
                        try:
                            part_num = int(match.group(1))
                            title = match.group(2).strip()
                            parts.append({
                                "number": part_num,
                                "title": title[:50]
                            })
                        except:
                            continue
                    
                    if debug_mode:
                        st.success(f"✓ Found {len(parts)} parts")
                        for p in parts:
                            st.write(f"  - Part {p['number']}: {p['title']}")
                
                # Step 4: Extract fields from each part
                all_fields = []
                for part in parts:
                    with st.spinner(f"Step 4: Extracting fields from Part {part['number']}..."):
                        # Get part text
                        part_pattern = f"Part\\s+{part['number']}\\b"
                        part_match = re.search(part_pattern, text, re.IGNORECASE)
                        
                        if part_match:
                            start = part_match.start()
                            end = min(start + 10000, len(text))
                            part_text = text[start:end]
                            
                            # Extract fields
                            fields = extract_fields_basic(part_text, part['number'])
                            all_fields.extend(fields)
                            
                            if debug_mode:
                                st.success(f"  ✓ Part {part['number']}: Found {len(fields)} fields")
                
                # Create result
                if all_fields:
                    st.success(f"✅ Extraction complete: {len(all_fields)} total fields from {len(parts)} parts")
                    
                    # Store in session state
                    result = create_extraction_result(form_number, parts, all_fields)
                    st.session_state.extraction_result = result
                    
                    # Show summary
                    with st.expander("Extraction Summary"):
                        for part in parts:
                            part_fields = [f for f in all_fields if f.get('part') == part['number']]
                            st.write(f"**Part {part['number']}**: {len(part_fields)} fields")
                            for field in part_fields[:5]:
                                st.write(f"  • {field['number']}: {field['label'][:50]}")
                else:
                    st.warning("⚠️ No fields extracted. The PDF might not be readable.")
                    
            except Exception as e:
                st.error(f"❌ Extraction failed: {str(e)}")
                if debug_mode:
                    st.exception(e)

def extract_fields_basic(text: str, part_number: int) -> List[Dict]:
    """Basic field extraction for debugging"""
    fields = []
    
    # Simple patterns
    patterns = [
        r'(\d+)\.([a-z])\.?\s+([^\n]{3,100})',  # 1.a. Field
        r'(\d+)\.\s+([^\n]{3,100})',  # 1. Field
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, text[:5000], re.IGNORECASE)
        for match in matches:
            if len(match.groups()) == 3:
                # Subfield
                fields.append({
                    'number': f"{match.group(1)}.{match.group(2)}",
                    'label': match.group(3).strip()[:100],
                    'part': part_number
                })
            elif len(match.groups()) == 2:
                # Main field
                fields.append({
                    'number': match.group(1),
                    'label': match.group(2).strip()[:100],
                    'part': part_number
                })
    
    return fields

def create_extraction_result(form_number: str, parts: List[Dict], fields: List[Dict]) -> ExtractionResult:
    """Create extraction result from basic data"""
    result = ExtractionResult(success=True)
    result.form_number = form_number
    result.form_title = f"USCIS Form {form_number}"
    
    # Group fields by part
    for part_info in parts:
        part = FormPart(
            number=part_info['number'],
            title=part_info['title']
        )
        
        # Add fields to part
        part_fields = [f for f in fields if f.get('part') == part.number]
        for field_data in part_fields:
            field = FormField(
                number=field_data['number'],
                label=field_data['label'],
                part_number=part.number,
                extraction_method="Basic"
            )
            part.fields.append(field)
        
        result.parts.append(part)
    
    result.stats = {
        'total_parts': len(result.parts),
        'total_fields': sum(len(p.fields) for p in result.parts)
    }
    
    return result
