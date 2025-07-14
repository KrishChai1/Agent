import streamlit as st
import requests
import json
import os
import time
from typing import Dict, List
from dotenv import load_dotenv
import openai
from datetime import datetime
from PIL import Image
import io
import zipfile

# Disable PIL max image pixels check
Image.MAX_IMAGE_PIXELS = None

# Load environment variables
load_dotenv()

# Configure page
st.set_page_config(
    page_title="Figma to Angular - AI Orchestrator",
    page_icon="🎨",
    layout="wide"
)

# Initialize OpenAI
if os.getenv("OPENAI_API_KEY"):
    openai.api_key = os.getenv("OPENAI_API_KEY")

class FigmaAgent:
    """Figma interactions"""
    
    def __init__(self, access_token: str = None):
        self.access_token = access_token
        self.base_url = "https://api.figma.com/v1"
        self.headers = {"X-Figma-Token": self.access_token} if access_token else {}
    
    def test_connection(self) -> bool:
        if not self.access_token:
            return False
        try:
            response = requests.get(f"{self.base_url}/me", headers=self.headers)
            return response.status_code == 200
        except:
            return False
    
    def get_file(self, file_key: str) -> Dict:
        url = f"{self.base_url}/files/{file_key}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def extract_components(self, file_data: Dict) -> List[Dict]:
        components = []
        
        def traverse_node(node: Dict):
            if node.get('type') in ['COMPONENT', 'FRAME']:
                components.append({
                    'id': node.get('id', f'comp_{len(components)}'),
                    'name': node.get('name', f'Component{len(components) + 1}'),
                    'type': self._classify_type(node.get('name', '')),
                    'properties': {}
                })
            
            if 'children' in node:
                for child in node['children']:
                    traverse_node(child)
        
        if 'document' in file_data:
            traverse_node(file_data['document'])
        
        return components[:10]  # Limit to 10
    
    def create_sample_components(self) -> List[Dict]:
        """Create sample components"""
        return [
            {'id': '1', 'name': 'NavigationBar', 'type': 'navbar', 'properties': {}},
            {'id': '2', 'name': 'HeroSection', 'type': 'hero', 'properties': {}},
            {'id': '3', 'name': 'LoginForm', 'type': 'form', 'properties': {}},
            {'id': '4', 'name': 'ContentCard', 'type': 'card', 'properties': {}},
            {'id': '5', 'name': 'ActionButton', 'type': 'button', 'properties': {}}
        ]
    
    def _classify_type(self, name: str) -> str:
        name_lower = name.lower()
        types = {
            'button': ['button', 'btn', 'cta'],
            'card': ['card', 'tile'],
            'navbar': ['nav', 'header', 'menu'],
            'form': ['form', 'login', 'signup'],
            'hero': ['hero', 'banner']
        }
        
        for type_name, keywords in types.items():
            if any(kw in name_lower for kw in keywords):
                return type_name
        return 'component'

class CodeGenerator:
    """Generate Angular code"""
    
    def generate_component(self, component: Dict) -> Dict:
        name = self._clean_name(component['name'])
        type_name = component.get('type', 'component')
        
        # TypeScript
        ts = f"""import {{ Component, Input, Output, EventEmitter }} from '@angular/core';

@Component({{
  selector: 'app-{name.lower()}',
  templateUrl: './{name.lower()}.component.html',
  styleUrls: ['./{name.lower()}.component.css']
}})
export class {name}Component {{
  @Input() data: any = {{}};
  @Output() action = new EventEmitter<any>();
  
  onClick(): void {{
    this.action.emit({{ type: 'click' }});
  }}
}}"""
        
        # HTML
        html_templates = {
            'button': '<button (click)="onClick()">{{ data.label || "Click Me" }}</button>',
            'card': '<div class="card"><h3>{{ data.title || "Card" }}</h3><p>{{ data.content || "Content" }}</p></div>',
            'navbar': '<nav><span>{{ data.title || "App" }}</span></nav>',
            'form': '<form><input placeholder="Email"><input type="password" placeholder="Password"><button>Submit</button></form>',
            'hero': '<div class="hero"><h1>{{ data.title || "Welcome" }}</h1><p>{{ data.subtitle || "Subtitle" }}</p></div>'
        }
        html = html_templates.get(type_name, '<div>{{ data | json }}</div>')
        
        # CSS
        css = f""".{type_name} {{
  padding: 20px;
  margin: 10px;
}}"""
        
        return {
            'name': name,
            'typescript': ts,
            'html': html,
            'css': css
        }
    
    def _clean_name(self, name: str) -> str:
        import re
        name = re.sub(r'[^a-zA-Z0-9]', '', name)
        return name[0].upper() + name[1:] if name else 'Component'

def create_zip(components: List[Dict]) -> bytes:
    """Create project ZIP"""
    buffer = io.BytesIO()
    
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Components
        for comp in components:
            name = comp['name'].lower()
            zf.writestr(f"src/app/{name}/{name}.component.ts", comp['typescript'])
            zf.writestr(f"src/app/{name}/{name}.component.html", comp['html'])
            zf.writestr(f"src/app/{name}/{name}.component.css", comp['css'])
        
        # package.json
        package = {
            "name": "figma-app",
            "version": "1.0.0",
            "scripts": {"start": "ng serve", "build": "ng build"},
            "dependencies": {
                "@angular/animations": "^15.0.0",
                "@angular/common": "^15.0.0",
                "@angular/compiler": "^15.0.0",
                "@angular/core": "^15.0.0",
                "@angular/forms": "^15.0.0",
                "@angular/platform-browser": "^15.0.0",
                "@angular/platform-browser-dynamic": "^15.0.0",
                "rxjs": "~7.5.0",
                "tslib": "^2.3.0",
                "zone.js": "~0.11.4"
            }
        }
        zf.writestr("package.json", json.dumps(package, indent=2))
        
        # app.module.ts
        imports = ["import { NgModule } from '@angular/core';",
                  "import { BrowserModule } from '@angular/platform-browser';",
                  "import { AppComponent } from './app.component';"]
        declarations = ["AppComponent"]
        
        for comp in components:
            name = comp['name']
            imports.append(f"import {{ {name}Component }} from './{name.lower()}/{name.lower()}.component';")
            declarations.append(f"{name}Component")
        
        module = f"""{chr(10).join(imports)}

@NgModule({{
  declarations: [{', '.join(declarations)}],
  imports: [BrowserModule],
  bootstrap: [AppComponent]
}})
export class AppModule {{ }}"""
        
        zf.writestr("src/app/app.module.ts", module)
        
        # app.component
        app_ts = """import { Component } from '@angular/core';

@Component({
  selector: 'app-root',
  template: '<h1>Figma Generated App</h1><div class="components">""" + ''.join([f'<app-{c["name"].lower()}></app-{c["name"].lower()}>' for c in components]) + """</div>',
  styles: ['.components { display: grid; gap: 20px; padding: 20px; }']
})
export class AppComponent {}"""
        
        zf.writestr("src/app/app.component.ts", app_ts)
        
        # main.ts
        zf.writestr("src/main.ts", """import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';
import { AppModule } from './app/app.module';

platformBrowserDynamic().bootstrapModule(AppModule);""")
        
        # index.html
        zf.writestr("src/index.html", """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Figma App</title>
  <base href="/">
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
  <app-root></app-root>
</body>
</html>""")
        
        # angular.json & tsconfig
        angular_json = {"version": 1, "projects": {"app": {"projectType": "application", "root": "", "sourceRoot": "src"}}}
        zf.writestr("angular.json", json.dumps(angular_json))
        
        tsconfig = {"compilerOptions": {"target": "ES2022", "module": "ES2022", "lib": ["ES2022", "dom"]}}
        zf.writestr("tsconfig.json", json.dumps(tsconfig))
        
        # README
        zf.writestr("README.md", f"""# Figma Generated App

## Install
\`\`\`bash
npm install
\`\`\`

## Run
\`\`\`bash
ng serve
\`\`\`

## Components
{chr(10).join(['- ' + c['name'] for c in components])}
""")
    
    return buffer.getvalue()

def main():
    st.title("🎨 Figma to Angular Generator")
    
    # Sidebar
    with st.sidebar:
        st.header("Configuration")
        
        api_key = st.text_input("OpenAI Key (Optional)", type="password", value=os.getenv("OPENAI_API_KEY", ""))
        if api_key:
            openai.api_key = api_key
        
        method = st.radio("Input Method:", ["Figma API", "Upload Image"])
    
    # Main
    if method == "Figma API":
        st.header("Connect to Figma")
        
        token = st.text_input("Figma Token", type="password")
        url = st.text_input("Figma URL", placeholder="https://www.figma.com/file/...")
        
        file_key = ""
        if url:
            import re
            match = re.search(r'/file/([a-zA-Z0-9]+)', url)
            if match:
                file_key = match[1]
                st.info(f"File key: {file_key}")
        
        if st.button("Generate", disabled=not (token and file_key)):
            try:
                with st.spinner("Generating..."):
                    agent = FigmaAgent(token)
                    file_data = agent.get_file(file_key)
                    components = agent.extract_components(file_data)
                    
                    if not components:
                        st.warning("No components found, using samples")
                        components = agent.create_sample_components()
                    
                    generator = CodeGenerator()
                    generated = [generator.generate_component(c) for c in components]
                    
                    zip_data = create_zip(generated)
                    
                st.success(f"✅ Generated {len(generated)} components!")
                st.download_button("📦 Download Angular Project", zip_data, "figma-angular.zip", mime="application/zip")
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    else:
        st.header("Upload Design")
        
        file = st.file_uploader("Choose image", type=['png', 'jpg', 'jpeg'])
        
        if file:
            st.info(f"📄 {file.name} ({file.size // 1024} KB)")
            
            if st.button("Generate"):
                try:
                    with st.spinner("Generating..."):
                        agent = FigmaAgent()
                        components = agent.create_sample_components()
                        
                        generator = CodeGenerator()
                        generated = [generator.generate_component(c) for c in components]
                        
                        zip_data = create_zip(generated)
                    
                    st.success(f"✅ Generated {len(generated)} components!")
                    st.download_button("📦 Download Angular Project", zip_data, "figma-angular.zip", mime="application/zip")
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
