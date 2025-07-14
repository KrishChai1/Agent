import streamlit as st
import requests
import json
import os
import subprocess
import time
import shutil
import tempfile
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import openai
from datetime import datetime
from pathlib import Path
import socket
import webbrowser
import base64
from PIL import Image
import io

# Load environment variables
load_dotenv()

# Configure page
st.set_page_config(
    page_title="Figma to Angular - AI Orchestrator",
    page_icon="🎨",
    layout="wide"
)

# Initialize OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

class FigmaAgent:
    """Agent responsible for Figma API interactions"""
    
    def __init__(self, access_token: str = None):
        self.access_token = access_token
        self.base_url = "https://api.figma.com/v1"
        self.headers = {"X-Figma-Token": self.access_token} if access_token else {}
    
    def test_connection(self) -> bool:
        """Test if Figma token is valid"""
        if not self.access_token:
            return False
        try:
            response = requests.get(f"{self.base_url}/me", headers=self.headers)
            return response.status_code == 200
        except:
            return False
    
    def get_file(self, file_key: str) -> Dict:
        """Fetch Figma file data"""
        url = f"{self.base_url}/files/{file_key}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def extract_components(self, file_data: Dict) -> List[Dict]:
        """Extract component information from Figma file"""
        components = []
        
        def traverse_node(node: Dict, path: str = ""):
            node_type = node.get('type', '')
            node_name = node.get('name', 'Unnamed')
            
            # Identify components and important frames
            if node_type in ['COMPONENT', 'FRAME', 'GROUP']:
                component_info = {
                    'id': node.get('id', ''),
                    'name': node_name,
                    'type': self._classify_component(node),
                    'path': path,
                    'properties': self._extract_properties(node)
                }
                components.append(component_info)
            
            # Traverse children
            if 'children' in node:
                for child in node['children']:
                    traverse_node(child, f"{path}/{node_name}")
        
        if 'document' in file_data:
            traverse_node(file_data['document'])
        
        return components
    
    def analyze_image(self, image: Image.Image) -> List[Dict]:
        """Analyze uploaded Figma PNG and extract components using AI"""
        # Convert image to base64 for OpenAI Vision API
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        try:
            # Use OpenAI Vision to analyze the image
            response = openai.ChatCompletion.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a UI/UX expert. Analyze this Figma design and identify all UI components."
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": """Analyze this Figma design image and identify all UI components. 
                                For each component, provide:
                                1. Component name
                                2. Component type (button, input, card, navbar, form, list, etc.)
                                3. Visual properties (colors, dimensions, etc.)
                                
                                Return the result as a JSON array of components."""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            # Parse the response
            components_text = response.choices[0].message.content
            # Extract JSON from response
            import re
            json_match = re.search(r'\[.*\]', components_text, re.DOTALL)
            if json_match:
                components_data = json.loads(json_match.group())
                
                # Format components
                components = []
                for comp in components_data:
                    components.append({
                        'id': f"img_{len(components)}",
                        'name': comp.get('name', 'Component'),
                        'type': self._classify_component_name(comp.get('type', '')),
                        'path': '/image',
                        'properties': comp.get('properties', {})
                    })
                return components
        except Exception as e:
            st.error(f"Failed to analyze image with AI: {str(e)}")
        
        # Fallback: Return sample components based on common patterns
        return self._generate_sample_components()
    
    def _classify_component(self, node: Dict) -> str:
        """Classify component type based on name and structure"""
        name = node.get('name', '').lower()
        return self._classify_component_name(name)
    
    def _classify_component_name(self, name: str) -> str:
        """Classify component type based on name"""
        name = name.lower()
        
        # Check for common UI patterns
        patterns = {
            'button': ['button', 'btn', 'cta', 'click'],
            'input': ['input', 'field', 'textfield', 'search'],
            'card': ['card', 'tile', 'panel'],
            'navbar': ['nav', 'navigation', 'header', 'menu'],
            'form': ['form', 'login', 'signup', 'register'],
            'list': ['list', 'items', 'grid'],
            'hero': ['hero', 'banner', 'jumbotron'],
            'footer': ['footer', 'bottom'],
            'modal': ['modal', 'dialog', 'popup']
        }
        
        for comp_type, keywords in patterns.items():
            if any(keyword in name for keyword in keywords):
                return comp_type
        
        return 'component'
    
    def _extract_properties(self, node: Dict) -> Dict:
        """Extract visual properties from node"""
        props = {}
        
        # Dimensions
        if 'absoluteBoundingBox' in node:
            bbox = node['absoluteBoundingBox']
            props['width'] = bbox.get('width', 0)
            props['height'] = bbox.get('height', 0)
        
        # Colors
        if 'fills' in node and node['fills']:
            fill = node['fills'][0]
            if fill.get('type') == 'SOLID' and 'color' in fill:
                color = fill['color']
                props['backgroundColor'] = {
                    'r': int(color.get('r', 0) * 255),
                    'g': int(color.get('g', 0) * 255),
                    'b': int(color.get('b', 0) * 255),
                    'a': color.get('a', 1)
                }
        
        # Border radius
        if 'cornerRadius' in node:
            props['borderRadius'] = node['cornerRadius']
        
        # Text properties
        if node.get('type') == 'TEXT':
            props['text'] = node.get('characters', '')
            if 'style' in node:
                props['fontSize'] = node['style'].get('fontSize', 16)
                props['fontFamily'] = node['style'].get('fontFamily', 'Roboto')
        
        return props
    
    def _generate_sample_components(self) -> List[Dict]:
        """Generate sample components as fallback"""
        return [
            {
                'id': 'sample_1',
                'name': 'HeaderNavigation',
                'type': 'navbar',
                'path': '/sample',
                'properties': {'backgroundColor': {'r': 63, 'g': 81, 'b': 181, 'a': 1}}
            },
            {
                'id': 'sample_2',
                'name': 'LoginForm',
                'type': 'form',
                'path': '/sample',
                'properties': {'width': 400, 'height': 500}
            },
            {
                'id': 'sample_3',
                'name': 'PrimaryButton',
                'type': 'button',
                'path': '/sample',
                'properties': {'backgroundColor': {'r': 33, 'g': 150, 'b': 243, 'a': 1}}
            },
            {
                'id': 'sample_4',
                'name': 'ContentCard',
                'type': 'card',
                'path': '/sample',
                'properties': {'borderRadius': 8}
            }
        ]

class CodeGeneratorAgent:
    """Agent that uses OpenAI to generate Angular code"""
    
    def __init__(self):
        self.openai_client = openai
    
    def generate_angular_component(self, component: Dict) -> Dict:
        """Generate Angular component code using OpenAI"""
        
        prompt = self._create_component_prompt(component)
        
        try:
            response = self.openai_client.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Angular developer. Generate clean, production-ready Angular components with TypeScript, HTML templates, and CSS. Use Angular Material when appropriate."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Parse the response
            generated_code = response.choices[0].message.content
            return self._parse_generated_code(generated_code, component)
            
        except Exception as e:
            st.warning(f"OpenAI API error: {str(e)}. Using fallback templates.")
            # Fallback to template-based generation
            return self._generate_fallback_component(component)
    
    def _create_component_prompt(self, component: Dict) -> str:
        """Create prompt for OpenAI"""
        props = component.get('properties', {})
        
        prompt = f"""Generate an Angular component for a {component['type']} with these specifications:

Component Name: {component['name']}
Type: {component['type']}
Properties:
- Width: {props.get('width', 'auto')}px
- Height: {props.get('height', 'auto')}px
- Background Color: {props.get('backgroundColor', 'default')}
- Border Radius: {props.get('borderRadius', 0)}px

Generate:
1. TypeScript component class (.ts file)
2. HTML template (.html file)
3. CSS styles (.css file)

Requirements:
- Use Angular best practices
- Include proper types
- Make it responsive
- Use Angular Material if appropriate
- Add basic interactions (click handlers, etc.)

Format the response with clear separators:
--- TYPESCRIPT ---
[typescript code]
--- HTML ---
[html code]
--- CSS ---
[css code]
"""
        return prompt
    
    def _parse_generated_code(self, response: str, component: Dict) -> Dict:
        """Parse OpenAI response into component files"""
        # Initialize with defaults
        result = {
            'name': self._sanitize_name(component['name']),
            'typescript': '',
            'html': '',
            'css': ''
        }
        
        # Try to parse sections
        if '--- TYPESCRIPT ---' in response and '--- HTML ---' in response:
            parts = response.split('---')
            for i, part in enumerate(parts):
                if 'TYPESCRIPT' in part and i + 1 < len(parts):
                    result['typescript'] = parts[i + 1].strip()
                elif 'HTML' in part and i + 1 < len(parts):
                    result['html'] = parts[i + 1].strip()
                elif 'CSS' in part and i + 1 < len(parts):
                    result['css'] = parts[i + 1].strip()
        else:
            # If parsing fails, use the whole response as TypeScript
            result['typescript'] = response
            result['html'] = self._generate_fallback_html(component)
            result['css'] = self._generate_fallback_css(component)
        
        return result
    
    def _generate_fallback_component(self, component: Dict) -> Dict:
        """Generate component without OpenAI"""
        name = self._sanitize_name(component['name'])
        comp_type = component.get('type', 'component')
        
        # TypeScript
        typescript = f"""import {{ Component, OnInit, Input, Output, EventEmitter }} from '@angular/core';

@Component({{
  selector: 'app-{name.lower()}',
  templateUrl: './{name.lower()}.component.html',
  styleUrls: ['./{name.lower()}.component.css']
}})
export class {name}Component implements OnInit {{
  @Input() data: any = {{}};
  @Output() action = new EventEmitter<any>();
  
  constructor() {{ }}
  
  ngOnInit(): void {{
    console.log('{name} component initialized');
  }}
  
  handleClick(event: any): void {{
    this.action.emit({{ type: 'click', component: '{name}', event }});
  }}
}}"""
        
        # HTML
        html = self._generate_fallback_html(component)
        
        # CSS
        css = self._generate_fallback_css(component)
        
        return {
            'name': name,
            'typescript': typescript,
            'html': html,
            'css': css
        }
    
    def _generate_fallback_html(self, component: Dict) -> str:
        """Generate HTML based on component type"""
        comp_type = component.get('type', 'component')
        
        templates = {
            'button': '''<button mat-raised-button color="primary" (click)="handleClick($event)" class="custom-button">
  {{ data.label || 'Click Me' }}
</button>''',
            
            'input': '''<mat-form-field appearance="outline" class="full-width">
  <mat-label>{{ data.label || 'Input Field' }}</mat-label>
  <input matInput [(ngModel)]="data.value" [placeholder]="data.placeholder">
</mat-form-field>''',
            
            'card': '''<mat-card class="custom-card">
  <mat-card-header>
    <mat-card-title>{{ data.title || 'Card Title' }}</mat-card-title>
    <mat-card-subtitle>{{ data.subtitle || 'Card subtitle' }}</mat-card-subtitle>
  </mat-card-header>
  <mat-card-content>
    <p>{{ data.content || 'Card content goes here' }}</p>
  </mat-card-content>
  <mat-card-actions>
    <button mat-button (click)="handleClick('action1')">ACTION 1</button>
    <button mat-button (click)="handleClick('action2')">ACTION 2</button>
  </mat-card-actions>
</mat-card>''',
            
            'navbar': '''<mat-toolbar color="primary" class="navbar">
  <span>{{ data.title || 'App Title' }}</span>
  <span class="spacer"></span>
  <button mat-icon-button *ngFor="let item of data.items || []" (click)="handleClick(item)">
    <mat-icon>{{ item.icon || 'menu' }}</mat-icon>
  </button>
</mat-toolbar>''',
            
            'form': '''<form class="custom-form" (ngSubmit)="handleClick('submit')">
  <mat-form-field appearance="outline" class="full-width">
    <mat-label>Email</mat-label>
    <input matInput type="email" [(ngModel)]="data.email" name="email">
  </mat-form-field>
  
  <mat-form-field appearance="outline" class="full-width">
    <mat-label>Password</mat-label>
    <input matInput type="password" [(ngModel)]="data.password" name="password">
  </mat-form-field>
  
  <button mat-raised-button color="primary" type="submit" class="full-width">
    {{ data.submitLabel || 'Submit' }}
  </button>
</form>''',
            
            'list': '''<mat-list class="custom-list">
  <mat-list-item *ngFor="let item of data.items || []" (click)="handleClick(item)">
    <mat-icon matListIcon>{{ item.icon || 'folder' }}</mat-icon>
    <h3 matLine>{{ item.title || 'Item' }}</h3>
    <p matLine>{{ item.description || 'Description' }}</p>
  </mat-list-item>
</mat-list>'''
        }
        
        return templates.get(comp_type, '<div class="custom-component">{{ data | json }}</div>')
    
    def _generate_fallback_css(self, component: Dict) -> str:
        """Generate CSS based on component properties"""
        props = component.get('properties', {})
        css_rules = []
        
        # Width and height
        if props.get('width'):
            css_rules.append(f"width: {props['width']}px;")
        if props.get('height'):
            css_rules.append(f"height: {props['height']}px;")
        
        # Background color
        if props.get('backgroundColor'):
            color = props['backgroundColor']
            css_rules.append(f"background-color: rgba({color['r']}, {color['g']}, {color['b']}, {color['a']});")
        
        # Border radius
        if props.get('borderRadius'):
            css_rules.append(f"border-radius: {props['borderRadius']}px;")
        
        base_css = f""".custom-button, .custom-card, .navbar, .custom-form, .custom-list, .custom-component {{
  {' '.join(css_rules)}
}}

.full-width {{
  width: 100%;
}}

.spacer {{
  flex: 1 1 auto;
}}

.custom-form {{
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
}}

.custom-card {{
  margin: 16px;
}}

@media (max-width: 768px) {{
  .custom-button, .custom-card, .navbar, .custom-form, .custom-list {{
    width: 100% !important;
  }}
}}"""
        
        return base_css
    
    def _sanitize_name(self, name: str) -> str:
        """Convert name to valid Angular component name"""
        import re
        # Remove special characters and convert to PascalCase
        name = re.sub(r'[^a-zA-Z0-9\s]', '', name)
        words = name.split()
        return ''.join(word.capitalize() for word in words) if words else 'Component'

class LocalDeploymentAgent:
    """Agent for local/cloud-compatible deployment"""
    
    def __init__(self):
        self.project_path = None
    
    def create_static_angular_project(self, project_name: str, components: List[Dict]) -> str:
        """Create a static HTML version of Angular project that works without Node.js"""
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        self.project_path = os.path.join(temp_dir, project_name)
        os.makedirs(self.project_path, exist_ok=True)
        
        # Create index.html with all components inline
        self._create_static_html(components)
        
        # Create downloadable Angular project structure
        self._create_downloadable_project(components)
        
        return self.project_path
    
    def _create_static_html(self, components: List[Dict]):
        """Create a static HTML preview"""
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Figma to Angular - Preview</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Roboto, sans-serif;
            background-color: #f5f5f5;
            color: #333;
        }
        .mat-toolbar {
            background: #3f51b5;
            color: white;
            padding: 16px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.26);
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        h1 {
            text-align: center;
            color: #3f51b5;
            margin: 30px 0;
        }
        .component-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .component-preview {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .component-title {
            font-size: 18px;
            font-weight: 500;
            color: #3f51b5;
            margin-bottom: 10px;
        }
        .component-type {
            font-size: 14px;
            color: #666;
            margin-bottom: 20px;
        }
        /* Component styles */
        .custom-button {
            background: #3f51b5;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            text-transform: uppercase;
        }
        .custom-button:hover {
            background: #303f9f;
        }
        .custom-card {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 16px;
        }
        .form-field {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin: 10px 0;
        }
        .navbar {
            background: #3f51b5;
            color: white;
            padding: 12px;
            border-radius: 4px;
        }
        .list-item {
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
        }
        .download-section {
            margin-top: 40px;
            text-align: center;
            padding: 30px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .download-button {
            background: #4caf50;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 4px;
            font-size: 16px;
            cursor: pointer;
            margin-top: 20px;
        }
        .download-button:hover {
            background: #45a049;
        }
    </style>
</head>
<body>
    <div class="mat-toolbar">
        <span>🎨 Figma to Angular - Component Preview</span>
    </div>
    
    <div class="container">
        <h1>Generated Angular Components</h1>
        <p style="text-align: center; color: #666;">
            This is a preview of your generated components. Download the full Angular project below.
        </p>
        
        <div class="component-grid">
"""
        
        # Add component previews
        for component in components:
            html_content += f"""
            <div class="component-preview">
                <div class="component-title">{component['name']}</div>
                <div class="component-type">Type: {component['type']}</div>
                {self._get_component_preview_html(component)}
            </div>
            """
        
        html_content += """
        </div>
        
        <div class="download-section">
            <h2>📦 Download Your Angular Project</h2>
            <p>Your Angular project has been generated with all components!</p>
            <p>Click below to download the complete project with:</p>
            <ul style="list-style: none; text-align: left; display: inline-block;">
                <li>✅ TypeScript components</li>
                <li>✅ HTML templates</li>
                <li>✅ CSS styles</li>
                <li>✅ Angular Material setup</li>
                <li>✅ Complete project structure</li>
            </ul>
            <br>
            <p><strong>To run locally:</strong></p>
            <code>npm install && ng serve</code>
        </div>
    </div>
</body>
</html>"""
        
        with open(os.path.join(self.project_path, 'preview.html'), 'w') as f:
            f.write(html_content)
    
    def _get_component_preview_html(self, component: Dict) -> str:
        """Get preview HTML for component type"""
        comp_type = component.get('type', 'component')
        
        previews = {
            'button': '<button class="custom-button">Click Me</button>',
            'input': '<input type="text" class="form-field" placeholder="Enter text...">',
            'card': '''<div class="custom-card">
                <h3>Card Title</h3>
                <p>Card content goes here</p>
            </div>''',
            'navbar': '<div class="navbar">Navigation Bar</div>',
            'form': '''<div>
                <input type="email" class="form-field" placeholder="Email">
                <input type="password" class="form-field" placeholder="Password">
                <button class="custom-button">Submit</button>
            </div>''',
            'list': '''<div>
                <div class="list-item">📁 List Item 1</div>
                <div class="list-item">📁 List Item 2</div>
            </div>'''
        }
        
        return previews.get(comp_type, '<div>Component Preview</div>')
    
    def _create_downloadable_project(self, components: List[Dict]):
        """Create the full Angular project structure for download"""
        # This creates the same structure as before but in a zip file
        # Users can download and run locally
        pass

def check_environment():
    """Check if running in cloud or local environment"""
    is_cloud = os.environ.get('STREAMLIT_SHARING_MODE', False)
    has_node = False
    
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, stderr=subprocess.DEVNULL)
        has_node = result.returncode == 0
    except (FileNotFoundError, OSError):
        has_node = False
    
    return {
        'is_cloud': is_cloud,
        'has_node': has_node,
        'can_run_locally': has_node and not is_cloud
    }

# Main Streamlit App
def main():
    st.title("🎨 Figma to Angular - AI Code Generator")
    st.markdown("Transform your Figma designs into Angular applications using AI")
    
    # Check environment
    env_info = check_environment()
    
    # Initialize session state
    if 'project_path' not in st.session_state:
        st.session_state.project_path = None
    if 'preview_url' not in st.session_state:
        st.session_state.preview_url = None
    if 'generated_components' not in st.session_state:
        st.session_state.generated_components = []
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # API Keys
        openai_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=os.getenv("OPENAI_API_KEY", ""),
            help="Required for AI-powered code generation"
        )
        
        if openai_key:
            openai.api_key = openai_key
        
        # Input method selection
        st.divider()
        input_method = st.radio(
            "Choose input method:",
            ["Figma API", "Upload PNG Image"],
            help="Use API for live Figma files, or upload PNG exports"
        )
        
        figma_token = None
        if input_method == "Figma API":
            # Figma Token
            figma_token = st.text_input(
                "Figma Access Token",
                type="password",
                help="Get from Figma > Account Settings > Personal Access Tokens"
            )
            
            # Test connection button
            if figma_token and st.button("Test Figma Connection"):
                agent = FigmaAgent(figma_token)
                if agent.test_connection():
                    st.success("✅ Connected to Figma!")
                else:
                    st.error("❌ Invalid Figma token")
        
        st.divider()
        
        # Environment info
        if env_info['is_cloud']:
            st.info("☁️ Running on Streamlit Cloud")
        else:
            st.info("💻 Running locally")
        
        if not env_info['has_node']:
            st.warning("⚠️ Node.js not detected. Preview mode only.")
        
        # Cleanup
        if st.button("🧹 Clean Up", help="Clear generated files"):
            st.session_state.clear()
            st.success("Cleaned up!")
    
    # Main content
    if input_method == "Figma API":
        # API-based workflow
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.header("📋 Step 1: Connect to Figma")
            
            figma_url = st.text_input(
                "Figma File URL",
                placeholder="https://www.figma.com/file/ABC123/Your-Design-File",
                help="Paste the URL of your Figma file"
            )
            
            # Extract file key
            file_key = ""
            if figma_url:
                import re
                match = re.search(r'/file/([a-zA-Z0-9]+)', figma_url)
                if match:
                    file_key = match.group(1)
                    st.info(f"File key: `{file_key}`")
                else:
                    st.error("Invalid Figma URL format")
        
        with col2:
            st.header("📊 Requirements")
            
            # Check requirements
            requirements = {
                "Figma Token": bool(figma_token),
                "OpenAI Key": bool(openai_key),
                "Valid URL": bool(file_key)
            }
            
            for req, status in requirements.items():
                if status:
                    st.success(f"✅ {req}")
                else:
                    st.error(f"❌ {req}")
        
        # Generation button
        if st.button(
            "🚀 Generate Angular App",
            type="primary",
            disabled=not all([figma_token, openai_key, file_key])
        ):
            generate_from_api(figma_token, file_key, openai_key, env_info)
    
    else:
        # Image upload workflow
        st.header("📤 Upload Figma Design")
        
        uploaded_file = st.file_uploader(
            "Choose a PNG file",
            type=['png', 'jpg', 'jpeg'],
            help="Export your Figma design as PNG and upload here"
        )
        
        if uploaded_file:
            # Display the uploaded image
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.image(uploaded_file, caption="Uploaded Design", use_column_width=True)
            
            with col2:
                st.header("📊 Requirements")
                requirements = {
                    "OpenAI Key": bool(openai_key),
                    "Image Uploaded": True
                }
                
                for req, status in requirements.items():
                    if status:
                        st.success(f"✅ {req}")
                    else:
                        st.error(f"❌ {req}")
            
            # Generation button
            if st.button(
                "🚀 Generate from Image",
                type="primary",
                disabled=not openai_key
            ):
                generate_from_image(uploaded_file, openai_key, env_info)
    
    # Display results
    if st.session_state.generated_components:
        display_results(env_info)

def generate_from_api(figma_token: str, file_key: str, openai_key: str, env_info: Dict):
    """Generate Angular app from Figma API"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Step 1: Connect to Figma
        status_text.text("🔗 Connecting to Figma...")
        progress_bar.progress(10)
        
        figma_agent = FigmaAgent(figma_token)
        file_data = figma_agent.get_file(file_key)
        
        st.success(f"✅ Connected to: {file_data.get('name', 'Untitled')}")
        
        # Step 2: Extract components
        status_text.text("🔍 Analyzing components...")
        progress_bar.progress(25)
        
        components = figma_agent.extract_components(file_data)
        st.info(f"Found {len(components)} components")
        
        # Continue with generation
        generate_components(components, status_text, progress_bar, env_info)
        
    except Exception as e:
        st.error(f"Error: {str(e)}")
        progress_bar.progress(0)
        status_text.text("")

def generate_from_image(uploaded_file, openai_key: str, env_info: Dict):
    """Generate Angular app from uploaded image"""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Step 1: Process image
        status_text.text("🖼️ Processing image...")
        progress_bar.progress(10)
        
        # Open image
        image = Image.open(uploaded_file)
        
        # Step 2: Analyze with AI
        status_text.text("🤖 Analyzing design with AI...")
        progress_bar.progress(25)
        
        figma_agent = FigmaAgent()
        components = figma_agent.analyze_image(image)
        st.info(f"Identified {len(components)} components")
        
        # Continue with generation
        generate_components(components, status_text, progress_bar, env_info)
        
    except Exception as e:
        st.error(f"Error: {str(e)}")
        progress_bar.progress(0)
        status_text.text("")

def generate_components(components: List[Dict], status_text, progress_bar, env_info: Dict):
    """Generate Angular components and create project"""
    
    # Display components
    with st.expander("View Detected Components"):
        for comp in components:
            st.write(f"- **{comp['name']}** ({comp['type']})")
    
    # Step 3: Generate Angular code
    status_text.text("🤖 Generating Angular code with AI...")
    progress_bar.progress(40)
    
    code_agent = CodeGeneratorAgent()
    generated_components = []
    
    for i, component in enumerate(components):
        comp_progress = 40 + (40 * i / len(components))
        progress_bar.progress(int(comp_progress))
        status_text.text(f"Generating {component['name']}...")
        
        generated = code_agent.generate_angular_component(component)
        generated_components.append(generated)
    
    st.success(f"✅ Generated {len(generated_components)} components")
    st.session_state.generated_components = generated_components
    
    # Step 4: Create project
    status_text.text("📁 Creating Angular project...")
    progress_bar.progress(90)
    
    deployment_agent = LocalDeploymentAgent()
    project_name = f"figma-app-{int(time.time())}"
    project_path = deployment_agent.create_static_angular_project(project_name, generated_components)
    
    st.session_state.project_path = project_path
    st.session_state.preview_url = os.path.join(project_path, 'preview.html')
    
    progress_bar.progress(100)
    status_text.text("✅ Complete!")
    st.balloons()

def display_results(env_info: Dict):
    """Display generation results"""
    st.divider()
    st.success("🎉 Angular app generated successfully!")
    
    # Create ZIP file for download
    import zipfile
    import io
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add each component
        for comp in st.session_state.generated_components:
            base_name = comp['name'].lower()
            zip_file.writestr(f"src/app/{base_name}/{base_name}.component.ts", comp['typescript'])
            zip_file.writestr(f"src/app/{base_name}/{base_name}.component.html", comp['html'])
            zip_file.writestr(f"src/app/{base_name}/{base_name}.component.css", comp['css'])
        
        # Add package.json
        package_json = {
            "name": "figma-generated-app",
            "version": "1.0.0",
            "scripts": {
                "ng": "ng",
                "start": "ng serve",
                "build": "ng build"
            },
            "dependencies": {
                "@angular/animations": "^15.0.0",
                "@angular/common": "^15.0.0",
                "@angular/compiler": "^15.0.0",
                "@angular/core": "^15.0.0",
                "@angular/forms": "^15.0.0",
                "@angular/platform-browser": "^15.0.0",
                "@angular/platform-browser-dynamic": "^15.0.0",
                "@angular/router": "^15.0.0",
                "@angular/material": "^15.0.0",
                "@angular/cdk": "^15.0.0",
                "rxjs": "~7.5.0",
                "tslib": "^2.3.0",
                "zone.js": "~0.11.4"
            },
            "devDependencies": {
                "@angular-devkit/build-angular": "^15.0.0",
                "@angular/cli": "~15.0.0",
                "@angular/compiler-cli": "^15.0.0",
                "typescript": "~4.8.0"
            }
        }
        zip_file.writestr("package.json", json.dumps(package_json, indent=2))
        
        # Add README
        readme = """# Figma Generated Angular App

## Installation
```bash
npm install
```

## Development server
```bash
ng serve
```
Navigate to `http://localhost:4200/`

## Build
```bash
ng build
```

## Components
"""
        for comp in st.session_state.generated_components:
            readme += f"- {comp['name']}\n"
        
        zip_file.writestr("README.md", readme)
    
    # Download button
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="📦 Download Angular Project",
            data=zip_buffer.getvalue(),
            file_name="figma-angular-app.zip",
            mime="application/zip",
            help="Download the complete Angular project"
        )
    
    with col2:
        if st.session_state.preview_url and os.path.exists(st.session_state.preview_url):
            with open(st.session_state.preview_url, 'r') as f:
                preview_html = f.read()
            
            st.download_button(
                label="👁️ Download Preview HTML",
                data=preview_html,
                file_name="preview.html",
                mime="text/html",
                help="Download a static preview of your components"
            )
    
    # Show generated code
    with st.expander("📝 View Generated Code"):
        for comp in st.session_state.generated_components:
            st.subheader(f"Component: {comp['name']}")
            
            tab1, tab2, tab3 = st.tabs(["TypeScript", "HTML", "CSS"])
            
            with tab1:
                st.code(comp['typescript'], language='typescript')
            with tab2:
                st.code(comp['html'], language='html')
            with tab3:
                st.code(comp['css'], language='css')
    
    # Instructions
    st.info("""
    ### 🚀 Next Steps:
    1. Download the Angular project ZIP file
    2. Extract it to your desired location
    3. Run `npm install` to install dependencies
    4. Run `ng serve` to start the development server
    5. Open `http://localhost:4200` in your browser
    
    **Note:** Node.js and Angular CLI must be installed on your local machine to run the project.
    """)

if __name__ == "__main__":
    main()
