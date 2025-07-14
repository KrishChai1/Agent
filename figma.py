import streamlit as st
import requests
import json
import os
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import openai
from datetime import datetime
import re
import base64

# Load environment variables
load_dotenv()

# Configure OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

class FigmaAPI:
    """Enhanced Figma API client with design analysis capabilities"""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.figma.com/v1"
        self.headers = {
            "X-Figma-Token": self.access_token
        }
    
    def get_file(self, file_key: str) -> Dict:
        """Get Figma file details"""
        url = f"{self.base_url}/files/{file_key}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_file_nodes(self, file_key: str, node_ids: List[str]) -> Dict:
        """Get specific nodes from a Figma file"""
        node_ids_str = ",".join(node_ids)
        url = f"{self.base_url}/files/{file_key}/nodes?ids={node_ids_str}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_file_images(self, file_key: str, node_ids: List[str], format: str = "png", scale: float = 2) -> Dict:
        """Export images from Figma file"""
        node_ids_str = ",".join(node_ids)
        url = f"{self.base_url}/images/{file_key}?ids={node_ids_str}&format={format}&scale={scale}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def analyze_design_system(self, file_data: Dict) -> Dict:
        """Analyze Figma file for design system elements"""
        analysis = {
            "colors": {},
            "typography": {},
            "spacing": {},
            "components": {},
            "layout_patterns": []
        }
        
        # Extract colors
        if 'styles' in file_data:
            for style_id, style in file_data['styles'].items():
                if style.get('styleType') == 'FILL':
                    analysis['colors'][style['name']] = style
                elif style.get('styleType') == 'TEXT':
                    analysis['typography'][style['name']] = style
        
        # Extract components
        if 'components' in file_data:
            for comp_id, comp in file_data['components'].items():
                analysis['components'][comp['name']] = {
                    'id': comp_id,
                    'description': comp.get('description', ''),
                    'type': comp.get('type', 'COMPONENT')
                }
        
        # Analyze layout patterns
        def analyze_node(node: Dict, depth: int = 0):
            if depth > 10:  # Prevent deep recursion
                return
            
            node_type = node.get('type', '')
            if node_type in ['FRAME', 'GROUP', 'COMPONENT']:
                layout_info = {
                    'type': node_type,
                    'name': node.get('name', ''),
                    'layout': node.get('layoutMode', 'NONE'),
                    'padding': node.get('paddingLeft', 0),
                    'spacing': node.get('itemSpacing', 0)
                }
                if layout_info['layout'] != 'NONE':
                    analysis['layout_patterns'].append(layout_info)
            
            if 'children' in node:
                for child in node['children']:
                    analyze_node(child, depth + 1)
        
        if 'document' in file_data:
            analyze_node(file_data['document'])
        
        return analysis

class AngularCodeGenerator:
    """AI-powered Angular code generator from Figma designs"""
    
    def __init__(self):
        self.component_templates = {
            "button": self._generate_button_template,
            "card": self._generate_card_template,
            "form": self._generate_form_template,
            "navigation": self._generate_nav_template,
            "hero": self._generate_hero_template
        }
    
    def analyze_component_type(self, node: Dict) -> str:
        """Determine component type from Figma node"""
        name = node.get('name', '').lower()
        
        # Pattern matching for component types
        if any(keyword in name for keyword in ['button', 'btn', 'cta']):
            return 'button'
        elif any(keyword in name for keyword in ['card', 'tile', 'item']):
            return 'card'
        elif any(keyword in name for keyword in ['form', 'input', 'field']):
            return 'form'
        elif any(keyword in name for keyword in ['nav', 'menu', 'header']):
            return 'navigation'
        elif any(keyword in name for keyword in ['hero', 'banner', 'splash']):
            return 'hero'
        else:
            return 'generic'
    
    def generate_angular_component(self, figma_node: Dict, design_analysis: Dict) -> Dict:
        """Generate Angular component from Figma node"""
        component_type = self.analyze_component_type(figma_node)
        component_name = self._sanitize_component_name(figma_node.get('name', 'Component'))
        
        # Generate component files
        component_code = {
            'name': component_name,
            'type': component_type,
            'typescript': self._generate_typescript(component_name, figma_node),
            'template': self._generate_template(component_type, figma_node, design_analysis),
            'styles': self._generate_styles(figma_node, design_analysis),
            'spec': self._generate_spec(component_name)
        }
        
        return component_code
    
    def _sanitize_component_name(self, name: str) -> str:
        """Convert Figma name to valid Angular component name"""
        # Remove special characters and convert to PascalCase
        name = re.sub(r'[^a-zA-Z0-9\s]', '', name)
        words = name.split()
        return ''.join(word.capitalize() for word in words)
    
    def _generate_typescript(self, component_name: str, node: Dict) -> str:
        """Generate TypeScript component file"""
        return f"""import {{ Component, OnInit, Input, Output, EventEmitter }} from '@angular/core';

@Component({{
  selector: 'app-{component_name.lower()}',
  templateUrl: './{component_name.lower()}.component.html',
  styleUrls: ['./{component_name.lower()}.component.scss']
}})
export class {component_name}Component implements OnInit {{
  @Input() data: any;
  @Output() action = new EventEmitter<any>();
  
  constructor() {{ }}
  
  ngOnInit(): void {{
    // Initialize component
  }}
  
  onAction(event: any): void {{
    this.action.emit(event);
  }}
}}"""
    
    def _generate_template(self, component_type: str, node: Dict, design_analysis: Dict) -> str:
        """Generate HTML template based on component type"""
        if component_type in self.component_templates:
            return self.component_templates[component_type](node, design_analysis)
        else:
            return self._generate_generic_template(node)
    
    def _generate_button_template(self, node: Dict, design_analysis: Dict) -> str:
        """Generate button template"""
        text = node.get('name', 'Button')
        return f"""<button 
  class="custom-button" 
  (click)="onAction($event)"
  [attr.aria-label]="data?.ariaLabel || '{text}'">
  <span class="button-text">{{{{ data?.text || '{text}' }}}}</span>
  <mat-icon *ngIf="data?.icon">{{{{ data?.icon }}}}</mat-icon>
</button>"""
    
    def _generate_card_template(self, node: Dict, design_analysis: Dict) -> str:
        """Generate card template"""
        return """<mat-card class="custom-card">
  <mat-card-header *ngIf="data?.title || data?.subtitle">
    <mat-card-title>{{ data?.title }}</mat-card-title>
    <mat-card-subtitle>{{ data?.subtitle }}</mat-card-subtitle>
  </mat-card-header>
  
  <img mat-card-image *ngIf="data?.image" [src]="data?.image" [alt]="data?.imageAlt">
  
  <mat-card-content>
    <p>{{ data?.content }}</p>
  </mat-card-content>
  
  <mat-card-actions *ngIf="data?.actions">
    <button mat-button *ngFor="let action of data?.actions" 
            (click)="onAction(action)">
      {{ action.label }}
    </button>
  </mat-card-actions>
</mat-card>"""
    
    def _generate_form_template(self, node: Dict, design_analysis: Dict) -> str:
        """Generate form template"""
        return """<form class="custom-form" (ngSubmit)="onAction(formData)">
  <mat-form-field *ngFor="let field of data?.fields" appearance="outline">
    <mat-label>{{ field.label }}</mat-label>
    <input matInput 
           [type]="field.type || 'text'" 
           [placeholder]="field.placeholder"
           [(ngModel)]="formData[field.name]"
           [name]="field.name"
           [required]="field.required">
    <mat-error *ngIf="field.error">{{ field.error }}</mat-error>
  </mat-form-field>
  
  <div class="form-actions">
    <button mat-raised-button color="primary" type="submit">
      {{ data?.submitLabel || 'Submit' }}
    </button>
    <button mat-button type="button" (click)="onAction({type: 'cancel'})">
      {{ data?.cancelLabel || 'Cancel' }}
    </button>
  </div>
</form>"""
    
    def _generate_nav_template(self, node: Dict, design_analysis: Dict) -> str:
        """Generate navigation template"""
        return """<nav class="custom-navigation">
  <div class="nav-brand">
    <img *ngIf="data?.logo" [src]="data?.logo" alt="Logo">
    <span class="brand-text">{{ data?.brand }}</span>
  </div>
  
  <ul class="nav-links">
    <li *ngFor="let link of data?.links">
      <a [routerLink]="link.route" 
         routerLinkActive="active"
         (click)="onAction({type: 'navigate', link: link})">
        <mat-icon *ngIf="link.icon">{{ link.icon }}</mat-icon>
        <span>{{ link.label }}</span>
      </a>
    </li>
  </ul>
  
  <div class="nav-actions">
    <button mat-icon-button *ngFor="let action of data?.actions"
            (click)="onAction(action)"
            [matTooltip]="action.tooltip">
      <mat-icon>{{ action.icon }}</mat-icon>
    </button>
  </div>
</nav>"""
    
    def _generate_hero_template(self, node: Dict, design_analysis: Dict) -> str:
        """Generate hero section template"""
        return """<section class="hero-section">
  <div class="hero-content">
    <h1 class="hero-title">{{ data?.title }}</h1>
    <p class="hero-subtitle">{{ data?.subtitle }}</p>
    <div class="hero-actions">
      <button mat-raised-button color="primary" 
              *ngIf="data?.primaryAction"
              (click)="onAction(data?.primaryAction)">
        {{ data?.primaryAction?.label }}
      </button>
      <button mat-button 
              *ngIf="data?.secondaryAction"
              (click)="onAction(data?.secondaryAction)">
        {{ data?.secondaryAction?.label }}
      </button>
    </div>
  </div>
  <div class="hero-image" *ngIf="data?.image">
    <img [src]="data?.image" [alt]="data?.imageAlt">
  </div>
</section>"""
    
    def _generate_generic_template(self, node: Dict) -> str:
        """Generate generic template for unknown component types"""
        return """<div class="custom-component">
  <ng-content></ng-content>
</div>"""
    
    def _generate_styles(self, node: Dict, design_analysis: Dict) -> str:
        """Generate SCSS styles from Figma node properties"""
        styles = []
        
        # Extract styling properties
        if 'absoluteBoundingBox' in node:
            bounds = node['absoluteBoundingBox']
            styles.append(f"width: {bounds.get('width', 'auto')}px;")
            styles.append(f"height: {bounds.get('height', 'auto')}px;")
        
        if 'fills' in node and node['fills']:
            fill = node['fills'][0]
            if fill['type'] == 'SOLID':
                color = fill['color']
                rgba = f"rgba({int(color['r']*255)}, {int(color['g']*255)}, {int(color['b']*255)}, {color.get('a', 1)})"
                styles.append(f"background-color: {rgba};")
        
        if 'cornerRadius' in node:
            styles.append(f"border-radius: {node['cornerRadius']}px;")
        
        if 'paddingLeft' in node:
            styles.append(f"padding: {node.get('paddingTop', 0)}px {node.get('paddingRight', 0)}px {node.get('paddingBottom', 0)}px {node.get('paddingLeft', 0)}px;")
        
        # Generate SCSS
        scss = f""".custom-component {{
  {' '.join(styles)}
  
  // Responsive styles
  @media (max-width: 768px) {{
    width: 100%;
    padding: 1rem;
  }}
}}"""
        
        return scss
    
    def _generate_spec(self, component_name: str) -> str:
        """Generate test spec file"""
        return f"""import {{ ComponentFixture, TestBed }} from '@angular/core/testing';
import {{ {component_name}Component }} from './{component_name.lower()}.component';

describe('{component_name}Component', () => {{
  let component: {component_name}Component;
  let fixture: ComponentFixture<{component_name}Component>;

  beforeEach(async () => {{
    await TestBed.configureTestingModule({{
      declarations: [ {component_name}Component ]
    }})
    .compileComponents();
  }});

  beforeEach(() => {{
    fixture = TestBed.createComponent({component_name}Component);
    component = fixture.componentInstance;
    fixture.detectChanges();
  }});

  it('should create', () => {{
    expect(component).toBeTruthy();
  }});
  
  it('should emit action on button click', () => {{
    spyOn(component.action, 'emit');
    const testEvent = {{ type: 'test' }};
    component.onAction(testEvent);
    expect(component.action.emit).toHaveBeenCalledWith(testEvent);
  }});
}});"""
    
    def generate_ai_enhanced_code(self, figma_data: Dict, component_description: str) -> str:
        """Use AI to generate more sophisticated Angular code"""
        try:
            prompt = f"""
            Generate production-ready Angular component code based on this Figma design data:
            Component Description: {component_description}
            Figma Data Summary: {json.dumps(figma_data, indent=2)[:1000]}
            
            Requirements:
            1. Use Angular Material components
            2. Implement responsive design
            3. Include proper TypeScript typing
            4. Add accessibility features
            5. Include error handling
            6. Follow Angular best practices
            
            Generate complete component code including TypeScript, HTML template, and SCSS styles.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert Angular developer who converts Figma designs to production-ready Angular code."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
        except Exception as e:
            st.error(f"AI generation failed: {str(e)}")
            return None

class FigmaToAngularApp:
    """Main Streamlit application"""
    
    def __init__(self):
        self.setup_page_config()
        self.init_session_state()
        self.code_generator = AngularCodeGenerator()
    
    def setup_page_config(self):
        """Configure Streamlit page settings"""
        st.set_page_config(
            page_title="Figma to Angular Code Generator",
            page_icon="🎨",
            layout="wide",
            initial_sidebar_state="expanded"
        )
    
    def init_session_state(self):
        """Initialize session state variables"""
        if 'figma_client' not in st.session_state:
            st.session_state.figma_client = None
        if 'current_file' not in st.session_state:
            st.session_state.current_file = None
        if 'file_data' not in st.session_state:
            st.session_state.file_data = None
        if 'generated_code' not in st.session_state:
            st.session_state.generated_code = []
        if 'selected_nodes' not in st.session_state:
            st.session_state.selected_nodes = []
    
    def sidebar_content(self):
        """Sidebar with authentication and settings"""
        with st.sidebar:
            st.header("🔐 Authentication")
            
            # Figma Token
            figma_token = st.text_input(
                "Figma Access Token",
                value=os.getenv("FIGMA_ACCESS_TOKEN", ""),
                type="password",
                help="Get from Figma Account Settings"
            )
            
            # OpenAI API Key
            openai_key = st.text_input(
                "OpenAI API Key",
                value=os.getenv("OPENAI_API_KEY", ""),
                type="password",
                help="For AI-enhanced code generation"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Connect", type="primary"):
                    if figma_token:
                        try:
                            st.session_state.figma_client = FigmaAPI(figma_token)
                            if openai_key:
                                openai.api_key = openai_key
                            st.success("✅ Connected!")
                        except Exception as e:
                            st.error(f"Connection failed: {str(e)}")
                    else:
                        st.error("Please provide Figma token")
            
            with col2:
                if st.button("Disconnect"):
                    st.session_state.figma_client = None
                    st.session_state.current_file = None
                    st.session_state.file_data = None
                    st.info("Disconnected")
            
            st.divider()
            
            # Settings
            st.header("⚙️ Settings")
            
            st.checkbox("Use AI Enhancement", value=True, key="use_ai")
            st.selectbox(
                "Code Style",
                ["Angular Material", "Bootstrap", "Custom CSS"],
                key="code_style"
            )
            st.selectbox(
                "Component Naming",
                ["PascalCase", "kebab-case", "camelCase"],
                key="naming_convention"
            )
            
            st.divider()
            
            # Export Options
            st.header("📦 Export")
            if st.button("Download All Code", disabled=not st.session_state.generated_code):
                self.download_generated_code()
    
    def main_content(self):
        """Main application content"""
        st.title("🎨 Figma to Angular Code Generator")
        st.markdown("Convert your Figma designs into production-ready Angular components with AI assistance")
        
        if not st.session_state.figma_client:
            self.show_welcome_screen()
            return
        
        # File Input Section
        st.header("📁 Select Figma File")
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            file_url = st.text_input(
                "Figma File URL",
                placeholder="https://www.figma.com/file/...",
                help="Paste your Figma file URL here"
            )
        
        with col2:
            file_key = self.extract_file_key(file_url) if file_url else ""
            st.text_input("File Key", value=file_key, disabled=True)
        
        with col3:
            if st.button("Load File", type="primary", disabled=not file_key):
                self.load_figma_file(file_key)
        
        # Display loaded file info
        if st.session_state.file_data:
            self.display_file_info()
            
            # Component Selection
            st.header("🎯 Select Components")
            self.display_component_selector()
            
            # Code Generation
            st.header("⚡ Generate Angular Code")
            self.display_code_generator()
            
            # Generated Code Display
            if st.session_state.generated_code:
                st.header("📝 Generated Code")
                self.display_generated_code()
    
    def show_welcome_screen(self):
        """Display welcome screen for unauthenticated users"""
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("""
            ### 🚀 Get Started
            
            1. **Get Figma Access Token**
               - Go to Figma → Account Settings
               - Create Personal Access Token
               - Copy and paste in sidebar
            
            2. **Optional: Add OpenAI Key**
               - For AI-enhanced code generation
               - Get from OpenAI platform
            
            3. **Load Your Design**
               - Paste Figma file URL
               - Select components
               - Generate Angular code!
            """)
        
        with col2:
            st.markdown("""
            ### ✨ Features
            
            - **🎨 Design Analysis** - Extracts colors, typography, spacing
            - **🤖 AI-Powered** - Generates semantic, accessible code
            - **📦 Complete Components** - TypeScript, HTML, SCSS, Tests
            - **🎯 Angular Material** - Uses best practices
            - **♿ Accessible** - ARIA labels and semantic HTML
            - **📱 Responsive** - Mobile-first approach
            """)
    
    def extract_file_key(self, url: str) -> str:
        """Extract file key from Figma URL"""
        import re
        match = re.search(r'/file/([a-zA-Z0-9]+)', url)
        return match.group(1) if match else ""
    
    def load_figma_file(self, file_key: str):
        """Load Figma file data"""
        with st.spinner("Loading Figma file..."):
            try:
                file_data = st.session_state.figma_client.get_file(file_key)
                st.session_state.file_data = file_data
                st.session_state.current_file = file_key
                st.success(f"✅ Loaded: {file_data.get('name', 'Untitled')}")
                
                # Analyze design system
                analysis = st.session_state.figma_client.analyze_design_system(file_data)
                st.session_state.design_analysis = analysis
                
            except Exception as e:
                st.error(f"Failed to load file: {str(e)}")
    
    def display_file_info(self):
        """Display loaded file information"""
        file_data = st.session_state.file_data
        
        with st.expander("📊 File Information", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("File Name", file_data.get('name', 'Unknown'))
            with col2:
                st.metric("Last Modified", file_data.get('lastModified', 'Unknown')[:10])
            with col3:
                st.metric("Components", len(file_data.get('components', {})))
            with col4:
                st.metric("Styles", len(file_data.get('styles', {})))
            
            # Design System Summary
            if hasattr(st.session_state, 'design_analysis'):
                analysis = st.session_state.design_analysis
                st.markdown("### 🎨 Design System")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Colors:** {len(analysis['colors'])}")
                    st.markdown(f"**Typography:** {len(analysis['typography'])}")
                with col2:
                    st.markdown(f"**Components:** {len(analysis['components'])}")
                    st.markdown(f"**Layout Patterns:** {len(analysis['layout_patterns'])}")
    
    def display_component_selector(self):
        """Display component selection interface"""
        components = st.session_state.file_data.get('components', {})
        
        if not components:
            st.warning("No components found in this file")
            return
        
        # Create selectable list
        component_options = []
        for comp_id, comp_data in components.items():
            option = f"{comp_data.get('name', 'Unnamed')} ({comp_data.get('description', 'No description')})"
            component_options.append((comp_id, option))
        
        selected = st.multiselect(
            "Select components to generate",
            options=[opt[1] for opt in component_options],
            default=[],
            help="Select one or more components to convert to Angular"
        )
        
        # Update selected nodes
        st.session_state.selected_nodes = [
            comp_id for comp_id, opt in component_options if opt in selected
        ]
        
        if st.session_state.selected_nodes:
            st.info(f"Selected {len(st.session_state.selected_nodes)} component(s)")
    
    def display_code_generator(self):
        """Display code generation controls"""
        col1, col2 = st.columns([3, 1])
        
        with col1:
            component_description = st.text_area(
                "Additional Context (Optional)",
                placeholder="Describe the component's purpose, interactions, or specific requirements...",
                height=100
            )
        
        with col2:
            st.markdown("### Options")
            include_tests = st.checkbox("Include Tests", value=True)
            include_stories = st.checkbox("Include Storybook", value=False)
            include_module = st.checkbox("Generate Module", value=True)
        
        if st.button("🚀 Generate Angular Code", type="primary", disabled=not st.session_state.selected_nodes):
            self.generate_code(component_description, include_tests, include_stories, include_module)
    
    def generate_code(self, description: str, include_tests: bool, include_stories: bool, include_module: bool):
        """Generate Angular code for selected components"""
        generated_components = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_components = len(st.session_state.selected_nodes)
        
        for idx, node_id in enumerate(st.session_state.selected_nodes):
            status_text.text(f"Generating component {idx + 1} of {total_components}...")
            
            # Get component data
            component_data = st.session_state.file_data['components'].get(node_id, {})
            
            # Get node details
            node_details = st.session_state.figma_client.get_file_nodes(
                st.session_state.current_file,
                [node_id]
            )
            
            # Generate base code
            generated_code = self.code_generator.generate_angular_component(
                component_data,
                st.session_state.design_analysis
            )
            
            # AI Enhancement if enabled
            if st.session_state.use_ai and openai.api_key:
                ai_code = self.code_generator.generate_ai_enhanced_code(
                    component_data,
                    description
                )
                if ai_code:
                    generated_code['ai_enhanced'] = ai_code
            
            generated_components.append(generated_code)
            progress_bar.progress((idx + 1) / total_components)
        
        st.session_state.generated_code = generated_components
        status_text.text("✅ Code generation complete!")
        st.success(f"Generated {len(generated_components)} component(s)")
    
    def display_generated_code(self):
        """Display generated code with syntax highlighting"""
        for idx, component in enumerate(st.session_state.generated_code):
            with st.expander(f"📦 {component['name']} Component", expanded=idx == 0):
                tabs = st.tabs(["TypeScript", "Template", "Styles", "Tests", "AI Enhanced"])
                
                with tabs[0]:
                    st.code(component['typescript'], language='typescript')
                
                with tabs[1]:
                    st.code(component['template'], language='html')
                
                with tabs[2]:
                    st.code(component['styles'], language='scss')
                
                with tabs[3]:
                    st.code(component['spec'], language='typescript')
                
                with tabs[4]:
                    if 'ai_enhanced' in component:
                        st.code(component['ai_enhanced'], language='typescript')
                    else:
                        st.info("AI enhancement not available")
                
                # Download button for this component
                if st.button(f"Download {component['name']}", key=f"download_{idx}"):
                    self.download_component(component)
    
    def download_component(self, component: Dict):
        """Download individual component files"""
        import zipfile
        import io
        
        # Create zip file in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            base_name = component['name'].lower()
            
            # Add files to zip
            zip_file.writestr(f"{base_name}/{base_name}.component.ts", component['typescript'])
            zip_file.writestr(f"{base_name}/{base_name}.component.html", component['template'])
            zip_file.writestr(f"{base_name}/{base_name}.component.scss", component['styles'])
            zip_file.writestr(f"{base_name}/{base_name}.component.spec.ts", component['spec'])
            
            if 'ai_enhanced' in component:
                zip_file.writestr(f"{base_name}/{base_name}.ai-enhanced.ts", component['ai_enhanced'])
        
        # Create download button
        st.download_button(
            label=f"Download {component['name']}.zip",
            data=zip_buffer.getvalue(),
            file_name=f"{base_name}.zip",
            mime="application/zip"
        )
    
    def download_generated_code(self):
        """Download all generated code as a zip file"""
        if not st.session_state.generated_code:
            return
        
        import zipfile
        import io
        
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add each component
            for component in st.session_state.generated_code:
                base_name = component['name'].lower()
                
                zip_file.writestr(f"components/{base_name}/{base_name}.component.ts", component['typescript'])
                zip_file.writestr(f"components/{base_name}/{base_name}.component.html", component['template'])
                zip_file.writestr(f"components/{base_name}/{base_name}.component.scss", component['styles'])
                zip_file.writestr(f"components/{base_name}/{base_name}.component.spec.ts", component['spec'])
            
            # Add module file
            module_content = self.generate_module_file()
            zip_file.writestr("components/components.module.ts", module_content)
            
            # Add README
            readme_content = self.generate_readme()
            zip_file.writestr("README.md", readme_content)
        
        st.sidebar.download_button(
            label="📦 Download All Components",
            data=zip_buffer.getvalue(),
            file_name="figma-angular-components.zip",
            mime="application/zip"
        )
    
    def generate_module_file(self) -> str:
        """Generate Angular module file for all components"""
        imports = []
        declarations = []
        
        for component in st.session_state.generated_code:
            name = component['name']
            imports.append(f"import {{ {name}Component }} from './{name.lower()}/{name.lower()}.component';")
            declarations.append(f"{name}Component")
        
        return f"""import {{ NgModule }} from '@angular/core';
import {{ CommonModule }} from '@angular/common';
import {{ MaterialModule }} from '../shared/material.module';

{chr(10).join(imports)}

@NgModule({{
  declarations: [
    {',\n    '.join(declarations)}
  ],
  imports: [
    CommonModule,
    MaterialModule
  ],
  exports: [
    {',\n    '.join(declarations)}
  ]
}})
export class ComponentsModule {{ }}"""
    
    def generate_readme(self) -> str:
        """Generate README file for the exported components"""
        return f"""# Figma to Angular Components

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Components

{chr(10).join([f"- {comp['name']} ({comp['type']})" for comp in st.session_state.generated_code])}

## Installation

1. Copy the components folder to your Angular project
2. Import ComponentsModule in your app.module.ts
3. Install Angular Material if not already installed:
   ```bash
   ng add @angular/material
   ```

## Usage

```typescript
import {{ ComponentsModule }} from './components/components.module';

@NgModule({{
  imports: [ComponentsModule]
}})
export class AppModule {{ }}
```

## Customization

Each component accepts a `data` input for dynamic content and emits `action` events for interactions.

Generated with Figma to Angular Code Generator
"""
    
    def run(self):
        """Main application entry point"""
        self.sidebar_content()
        self.main_content()

# Deployment configuration
def create_requirements_txt():
    """Generate requirements.txt for deployment"""
    requirements = """streamlit==1.28.1
requests==2.31.0
python-dotenv==1.0.0
openai==0.28.1
Pillow==10.1.0
"""
    return requirements

def create_dockerfile():
    """Generate Dockerfile for deployment"""
    dockerfile = """FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
"""
    return dockerfile

# Main execution
if __name__ == "__main__":
    # Check if running in deployment mode
    if os.getenv("GENERATE_DEPLOYMENT_FILES"):
        with open("requirements.txt", "w") as f:
            f.write(create_requirements_txt())
        with open("Dockerfile", "w") as f:
            f.write(create_dockerfile())
        print("Deployment files generated!")
    else:
        # Run the app
        app = FigmaToAngularApp()
        app.run()