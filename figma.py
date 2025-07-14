import streamlit as st
import requests
import json
import os
import time
import tempfile
from typing import Dict, List, Optional
from dotenv import load_dotenv
import openai
from datetime import datetime
import base64
from PIL import Image
import io
import zipfile

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
    
    def analyze_image_simple(self, image: Image.Image) -> List[Dict]:
        """Simple component extraction from image without AI"""
        # Return sample components for demonstration
        return [
            {
                'id': 'img_1',
                'name': 'NavigationBar',
                'type': 'navbar',
                'path': '/image',
                'properties': {'backgroundColor': {'r': 63, 'g': 81, 'b': 181, 'a': 1}}
            },
            {
                'id': 'img_2',
                'name': 'HeroSection',
                'type': 'hero',
                'path': '/image',
                'properties': {'width': 1200, 'height': 400}
            },
            {
                'id': 'img_3',
                'name': 'LoginForm',
                'type': 'form',
                'path': '/image',
                'properties': {'width': 400, 'height': 500}
            },
            {
                'id': 'img_4',
                'name': 'ContentCard',
                'type': 'card',
                'path': '/image',
                'properties': {'borderRadius': 8}
            },
            {
                'id': 'img_5',
                'name': 'ActionButton',
                'type': 'button',
                'path': '/image',
                'properties': {'backgroundColor': {'r': 76, 'g': 175, 'b': 80, 'a': 1}}
            }
        ]
    
    def _classify_component(self, node: Dict) -> str:
        """Classify component type based on name and structure"""
        name = node.get('name', '').lower()
        
        patterns = {
            'button': ['button', 'btn', 'cta', 'click'],
            'input': ['input', 'field', 'textfield', 'search'],
            'card': ['card', 'tile', 'panel'],
            'navbar': ['nav', 'navigation', 'header', 'menu'],
            'form': ['form', 'login', 'signup', 'register'],
            'list': ['list', 'items', 'grid'],
            'hero': ['hero', 'banner', 'jumbotron'],
            'footer': ['footer', 'bottom']
        }
        
        for comp_type, keywords in patterns.items():
            if any(keyword in name for keyword in keywords):
                return comp_type
        
        return 'component'
    
    def _extract_properties(self, node: Dict) -> Dict:
        """Extract visual properties from node"""
        props = {}
        
        if 'absoluteBoundingBox' in node:
            bbox = node['absoluteBoundingBox']
            props['width'] = bbox.get('width', 0)
            props['height'] = bbox.get('height', 0)
        
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
        
        if 'cornerRadius' in node:
            props['borderRadius'] = node['cornerRadius']
        
        return props

class CodeGeneratorAgent:
    """Agent that generates Angular code"""
    
    def __init__(self):
        self.use_ai = openai.api_key is not None
    
    def generate_angular_component(self, component: Dict) -> Dict:
        """Generate Angular component code"""
        if self.use_ai:
            try:
                return self._generate_with_ai(component)
            except:
                return self._generate_template_based(component)
        else:
            return self._generate_template_based(component)
    
    def _generate_with_ai(self, component: Dict) -> Dict:
        """Generate using OpenAI"""
        prompt = f"""Generate an Angular component for a {component['type']} named {component['name']}.
Generate TypeScript, HTML, and CSS code.
Format:
--- TYPESCRIPT ---
[code]
--- HTML ---
[code]
--- CSS ---
[code]"""
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an Angular expert."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500
        )
        
        return self._parse_ai_response(response.choices[0].message.content, component)
    
    def _generate_template_based(self, component: Dict) -> Dict:
        """Generate using templates"""
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
        
        # HTML templates by type
        html_templates = {
            'button': '<button class="btn btn-primary" (click)="handleClick($event)">{{ data.label || "Click Me" }}</button>',
            'card': '''<div class="card">
  <div class="card-header">{{ data.title || "Card Title" }}</div>
  <div class="card-body">
    <p>{{ data.content || "Card content" }}</p>
  </div>
</div>''',
            'navbar': '''<nav class="navbar">
  <span class="navbar-brand">{{ data.title || "App" }}</span>
  <div class="navbar-nav">
    <a class="nav-link" *ngFor="let item of data.items || []" (click)="handleClick(item)">
      {{ item.label }}
    </a>
  </div>
</nav>''',
            'form': '''<form (ngSubmit)="handleClick('submit')">
  <div class="form-group">
    <label>Email</label>
    <input type="email" class="form-control" [(ngModel)]="data.email" name="email">
  </div>
  <div class="form-group">
    <label>Password</label>
    <input type="password" class="form-control" [(ngModel)]="data.password" name="password">
  </div>
  <button type="submit" class="btn btn-primary">Submit</button>
</form>''',
            'hero': '''<div class="hero">
  <h1>{{ data.title || "Welcome" }}</h1>
  <p>{{ data.subtitle || "Build amazing apps" }}</p>
  <button class="btn btn-primary" (click)="handleClick('cta')">Get Started</button>
</div>''',
            'list': '''<ul class="list">
  <li *ngFor="let item of data.items || []" (click)="handleClick(item)">
    {{ item.title || "Item" }}
  </li>
</ul>'''
        }
        
        html = html_templates.get(comp_type, '<div class="component">{{ data | json }}</div>')
        
        # CSS
        props = component.get('properties', {})
        css_rules = []
        
        if props.get('backgroundColor'):
            color = props['backgroundColor']
            css_rules.append(f"background-color: rgba({color['r']}, {color['g']}, {color['b']}, {color['a']});")
        
        if props.get('width'):
            css_rules.append(f"width: {props['width']}px;")
        
        if props.get('borderRadius'):
            css_rules.append(f"border-radius: {props['borderRadius']}px;")
        
        css = f""".component, .card, .navbar, .hero, .btn {{
  {' '.join(css_rules)}
}}

.btn {{
  padding: 10px 20px;
  border: none;
  cursor: pointer;
}}

.card {{
  border: 1px solid #ddd;
  margin: 10px;
}}

.navbar {{
  display: flex;
  justify-content: space-between;
  padding: 10px;
}}

.hero {{
  text-align: center;
  padding: 50px;
}}"""
        
        return {
            'name': name,
            'typescript': typescript,
            'html': html,
            'css': css
        }
    
    def _parse_ai_response(self, response: str, component: Dict) -> Dict:
        """Parse AI response"""
        result = self._generate_template_based(component)
        
        if '--- TYPESCRIPT ---' in response:
            parts = response.split('---')
            for i, part in enumerate(parts):
                if 'TYPESCRIPT' in part and i + 1 < len(parts):
                    result['typescript'] = parts[i + 1].strip()
                elif 'HTML' in part and i + 1 < len(parts):
                    result['html'] = parts[i + 1].strip()
                elif 'CSS' in part and i + 1 < len(parts):
                    result['css'] = parts[i + 1].strip()
        
        return result
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitize component name"""
        import re
        name = re.sub(r'[^a-zA-Z0-9\s]', '', name)
        words = name.split()
        return ''.join(word.capitalize() for word in words) if words else 'Component'

def create_angular_project_zip(components: List[Dict]) -> bytes:
    """Create a ZIP file with the Angular project"""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add each component
        for comp in components:
            base_name = comp['name'].lower()
            comp_dir = f"src/app/{base_name}"
            
            zip_file.writestr(f"{comp_dir}/{base_name}.component.ts", comp['typescript'])
            zip_file.writestr(f"{comp_dir}/{base_name}.component.html", comp['html'])
            zip_file.writestr(f"{comp_dir}/{base_name}.component.css", comp['css'])
        
        # Add package.json
        package_json = {
            "name": "figma-angular-app",
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
                "@angular/material": "^15.0.0",
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
        
        # Add angular.json
        angular_json = {
            "version": 1,
            "projects": {
                "app": {
                    "projectType": "application",
                    "root": "",
                    "sourceRoot": "src",
                    "architect": {
                        "build": {
                            "builder": "@angular-devkit/build-angular:browser",
                            "options": {
                                "outputPath": "dist",
                                "index": "src/index.html",
                                "main": "src/main.ts",
                                "polyfills": ["zone.js"],
                                "tsConfig": "tsconfig.json",
                                "assets": ["src/assets"],
                                "styles": ["src/styles.css"],
                                "scripts": []
                            }
                        },
                        "serve": {
                            "builder": "@angular-devkit/build-angular:dev-server",
                            "options": {
                                "browserTarget": "app:build"
                            }
                        }
                    }
                }
            }
        }
        zip_file.writestr("angular.json", json.dumps(angular_json, indent=2))
        
        # Add tsconfig.json
        tsconfig = {
            "compilerOptions": {
                "baseUrl": "./",
                "outDir": "./dist/out-tsc",
                "sourceMap": True,
                "declaration": False,
                "downlevelIteration": True,
                "experimentalDecorators": True,
                "moduleResolution": "node",
                "importHelpers": True,
                "target": "ES2022",
                "module": "ES2022",
                "lib": ["ES2022", "dom"]
            }
        }
        zip_file.writestr("tsconfig.json", json.dumps(tsconfig, indent=2))
        
        # Add app.module.ts
        imports = ["import { NgModule } from '@angular/core';",
                  "import { BrowserModule } from '@angular/platform-browser';",
                  "import { FormsModule } from '@angular/forms';",
                  "import { AppComponent } from './app.component';"]
        
        declarations = ["AppComponent"]
        
        for comp in components:
            name = comp['name']
            imports.append(f"import {{ {name}Component }} from './{name.lower()}/{name.lower()}.component';")
            declarations.append(f"{name}Component")
        
        app_module = f"""{chr(10).join(imports)}

@NgModule({{
  declarations: [{', '.join(declarations)}],
  imports: [BrowserModule, FormsModule],
  providers: [],
  bootstrap: [AppComponent]
}})
export class AppModule {{ }}"""
        
        zip_file.writestr("src/app/app.module.ts", app_module)
        
        # Add app.component files
        app_component_ts = """import { Component } from '@angular/core';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  title = 'Figma Generated App';
}"""
        
        component_tags = [f'<app-{comp["name"].lower()}></app-{comp["name"].lower()}>' for comp in components]
        
        app_component_html = f"""<h1>{{{{ title }}}}</h1>
<div class="components">
{chr(10).join(component_tags)}
</div>"""
        
        app_component_css = """.components {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  padding: 20px;
}"""
        
        zip_file.writestr("src/app/app.component.ts", app_component_ts)
        zip_file.writestr("src/app/app.component.html", app_component_html)
        zip_file.writestr("src/app/app.component.css", app_component_css)
        
        # Add main.ts
        main_ts = """import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';
import { AppModule } from './app/app.module';

platformBrowserDynamic().bootstrapModule(AppModule);"""
        
        zip_file.writestr("src/main.ts", main_ts)
        
        # Add index.html
        index_html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Figma Angular App</title>
  <base href="/">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
  <app-root></app-root>
</body>
</html>"""
        
        zip_file.writestr("src/index.html", index_html)
        
        # Add styles.css
        styles_css = """body {
  font-family: Arial, sans-serif;
  margin: 0;
  padding: 0;
  background-color: #f5f5f5;
}"""
        
        zip_file.writestr("src/styles.css", styles_css)
        
        # Add README
        readme = f"""# Figma Generated Angular App

## Installation
\`\`\`bash
npm install
\`\`\`

## Development
\`\`\`bash
ng serve
\`\`\`

## Components Generated
{chr(10).join(['- ' + comp['name'] for comp in components])}

## Notes
- Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}
- Total components: {len(components)}
"""
        
        zip_file.writestr("README.md", readme)
    
    return zip_buffer.getvalue()

# Main App
def main():
    st.title("🎨 Figma to Angular - AI Code Generator")
    st.markdown("Transform your Figma designs into Angular applications")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # API Keys
        openai_key = st.text_input(
            "OpenAI API Key (Optional)",
            type="password",
            value=os.getenv("OPENAI_API_KEY", ""),
            help="For enhanced AI generation"
        )
        
        if openai_key:
            openai.api_key = openai_key
            st.success("✅ AI generation enabled")
        else:
            st.info("ℹ️ Using template-based generation")
        
        # Input method
        st.divider()
        input_method = st.radio(
            "Choose input method:",
            ["Figma API", "Upload Image"],
            help="API for live files, Image for quick demos"
        )
        
        # Info
        st.divider()
        st.info("""
        📌 **How it works:**
        1. Choose input method
        2. Provide Figma URL or image
        3. Generate Angular code
        4. Download project ZIP
        """)
    
    # Main content
    if input_method == "Figma API":
        # Figma API workflow
        st.header("🔗 Connect to Figma")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            figma_token = st.text_input(
                "Figma Access Token",
                type="password",
                help="Get from Figma → Account Settings → Personal Access Tokens"
            )
            
            figma_url = st.text_input(
                "Figma File URL",
                placeholder="https://www.figma.com/file/ABC123/Your-Design",
                help="Paste your Figma file URL"
            )
        
        with col2:
            st.write("### Status")
            if figma_token:
                agent = FigmaAgent(figma_token)
                if agent.test_connection():
                    st.success("✅ Token valid")
                else:
                    st.error("❌ Invalid token")
        
        # Extract file key
        file_key = ""
        if figma_url:
            import re
            match = re.search(r'/file/([a-zA-Z0-9]+)', figma_url)
            if match:
                file_key = match.group(1)
                st.info(f"File key: `{file_key}`")
        
        if st.button("🚀 Generate from Figma", disabled=not (figma_token and file_key)):
            generate_from_figma(figma_token, file_key)
    
    else:
        # Image upload workflow
        st.header("📤 Upload Design Image")
        
        uploaded_file = st.file_uploader(
            "Choose an image file",
            type=['png', 'jpg', 'jpeg'],
            help="Export your Figma frame as PNG"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.image(uploaded_file, caption="Uploaded Design", use_column_width=True)
            
            with col2:
                st.write("### Info")
                st.info(f"File: {uploaded_file.name}")
                st.info(f"Size: {uploaded_file.size // 1024} KB")
            
            if st.button("🚀 Generate from Image", type="primary"):
                generate_from_image(uploaded_file)

def generate_from_figma(token: str, file_key: str):
    """Generate from Figma API"""
    progress = st.progress(0)
    status = st.empty()
    
    try:
        # Connect to Figma
        status.text("Connecting to Figma...")
        progress.progress(20)
        
        agent = FigmaAgent(token)
        file_data = agent.get_file(file_key)
        
        st.success(f"✅ Loaded: {file_data.get('name', 'Untitled')}")
        
        # Extract components
        status.text("Analyzing components...")
        progress.progress(40)
        
        components = agent.extract_components(file_data)
        st.info(f"Found {len(components)} components")
        
        # Generate code
        generate_and_download(components, status, progress)
        
    except Exception as e:
        st.error(f"Error: {str(e)}")

def generate_from_image(uploaded_file):
    """Generate from uploaded image"""
    progress = st.progress(0)
    status = st.empty()
    
    try:
        # Process image
        status.text("Processing image...")
        progress.progress(20)
        
        image = Image.open(uploaded_file)
        agent = FigmaAgent()
        
        # Extract components (simplified without AI)
        status.text("Identifying components...")
        progress.progress(40)
        
        components = agent.analyze_image_simple(image)
        st.info(f"Generated {len(components)} sample components")
        
        # Generate code
        generate_and_download(components, status, progress)
        
    except Exception as e:
        st.error(f"Error: {str(e)}")

def generate_and_download(components: List[Dict], status, progress):
    """Generate Angular code and create download"""
    
    # Show components
    with st.expander("📋 Components Detected"):
        for comp in components:
            st.write(f"- **{comp['name']}** ({comp['type']})")
    
    # Generate code
    status.text("Generating Angular code...")
    progress.progress(60)
    
    generator = CodeGeneratorAgent()
    generated = []
    
    for i, comp in enumerate(components):
        code = generator.generate_angular_component(comp)
        generated.append(code)
        progress.progress(60 + (30 * i / len(components)))
    
    # Create ZIP
    status.text("Creating project...")
    progress.progress(90)
    
    zip_data = create_angular_project_zip(generated)
    
    progress.progress(100)
    status.text("✅ Complete!")
    
    # Success message
    st.balloons()
    st.success("🎉 Angular project generated successfully!")
    
    # Download button
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="📦 Download Angular Project",
            data=zip_data,
            file_name=f"figma-angular-{int(time.time())}.zip",
            mime="application/zip"
        )
    
    with col2:
        st.info("""
        **Next steps:**
        1. Extract the ZIP file
        2. Run `npm install`
        3. Run `ng serve`
        4. Open http://localhost:4200
        """)
    
    # Show generated code
    with st.expander("👀 Preview Generated Code"):
        for comp in generated[:3]:  # Show first 3
            st.subheader(comp['name'])
            tabs = st.tabs(["TypeScript", "HTML", "CSS"])
            
            with tabs[0]:
                st.code(comp['typescript'], language='typescript')
            with tabs[1]:
                st.code(comp['html'], language='html')
            with tabs[2]:
                st.code(comp['css'], language='css')

if __name__ == "__main__":
    main()
