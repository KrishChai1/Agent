import streamlit as st
import requests
import json
import os
import time
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import openai
from datetime import datetime
from PIL import Image
import io
import zipfile
import tempfile
import subprocess
import shutil
import threading
import socket
import signal
import sys
import atexit

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
            'button': '''<button class="btn" (click)="onClick()">{{ data.label || "Click Me" }}</button>''',
            'card': '''<div class="card">
  <h3>{{ data.title || "Card Title" }}</h3>
  <p>{{ data.content || "Card content goes here" }}</p>
  <button class="btn-sm" (click)="onClick()">Learn More</button>
</div>''',
            'navbar': '''<nav class="navbar">
  <div class="nav-brand">{{ data.title || "My App" }}</div>
  <div class="nav-links">
    <a href="#" *ngFor="let item of data.links || [{label: 'Home'}, {label: 'About'}, {label: 'Contact'}]">
      {{ item.label }}
    </a>
  </div>
</nav>''',
            'form': '''<form class="form" (submit)="onClick()">
  <h3>{{ data.title || "Login" }}</h3>
  <input type="email" placeholder="Email" class="input">
  <input type="password" placeholder="Password" class="input">
  <button type="submit" class="btn">Submit</button>
</form>''',
            'hero': '''<div class="hero">
  <h1>{{ data.title || "Welcome to Our App" }}</h1>
  <p>{{ data.subtitle || "Build amazing things with Angular" }}</p>
  <button class="btn btn-primary" (click)="onClick()">Get Started</button>
</div>'''
        }
        html = html_templates.get(type_name, '<div>{{ data | json }}</div>')
        
        # CSS
        css = f""".{type_name} {{
  padding: 20px;
  margin: 10px;
}}

.btn {{
  background: #3f51b5;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}}

.btn:hover {{
  background: #303f9f;
}}

.card {{
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 20px;
}}

.navbar {{
  background: #3f51b5;
  color: white;
  padding: 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}}

.navbar a {{
  color: white;
  text-decoration: none;
  margin: 0 10px;
}}

.form {{
  background: white;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  max-width: 400px;
}}

.input {{
  width: 100%;
  padding: 10px;
  margin: 10px 0;
  border: 1px solid #ddd;
  border-radius: 4px;
}}

.hero {{
  text-align: center;
  padding: 60px 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
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

class DeploymentAgent:
    """Deploy and run Angular app locally"""
    
    def __init__(self):
        self.project_dir = None
        self.server_process = None
        self.port = None
        self.deployment_thread = None
        
    def find_available_port(self, start_port=4200):
        """Find an available port starting from start_port"""
        for port in range(start_port, start_port + 100):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except:
                continue
        return None
    
    def check_node_installed(self):
        """Check if Node.js and npm are installed"""
        try:
            node_version = subprocess.run(['node', '--version'], 
                                        capture_output=True, 
                                        text=True,
                                        shell=True if sys.platform == 'win32' else False)
            npm_version = subprocess.run(['npm', '--version'], 
                                       capture_output=True, 
                                       text=True,
                                       shell=True if sys.platform == 'win32' else False)
            
            return node_version.returncode == 0 and npm_version.returncode == 0
        except:
            return False
    
    def check_angular_cli(self):
        """Check if Angular CLI is installed"""
        try:
            result = subprocess.run(['ng', 'version'], 
                                  capture_output=True, 
                                  text=True,
                                  shell=True if sys.platform == 'win32' else False)
            return result.returncode == 0
        except:
            return False
    
    def deploy(self, zip_data: bytes, progress_callback=None):
        """Deploy the Angular app from ZIP data"""
        try:
            # Create temporary directory
            self.project_dir = tempfile.mkdtemp(prefix="figma_angular_")
            
            # Extract ZIP
            if progress_callback:
                progress_callback(0.1, "Extracting project files...")
            
            zip_path = os.path.join(self.project_dir, "project.zip")
            with open(zip_path, 'wb') as f:
                f.write(zip_data)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.project_dir)
            
            os.remove(zip_path)
            
            # Install dependencies
            if progress_callback:
                progress_callback(0.3, "Installing dependencies (this may take a few minutes)...")
            
            npm_install = subprocess.run(
                ['npm', 'install'],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                shell=True if sys.platform == 'win32' else False
            )
            
            if npm_install.returncode != 0:
                raise Exception(f"npm install failed: {npm_install.stderr}")
            
            # Find available port
            self.port = self.find_available_port()
            if not self.port:
                raise Exception("No available ports found")
            
            # Start Angular dev server
            if progress_callback:
                progress_callback(0.8, f"Starting Angular dev server on port {self.port}...")
            
            # Use ng serve with specific port
            serve_cmd = ['npx', 'ng', 'serve', '--port', str(self.port), '--open=false']
            
            self.server_process = subprocess.Popen(
                serve_cmd,
                cwd=self.project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True if sys.platform == 'win32' else False
            )
            
            # Wait for server to start
            time.sleep(10)  # Give Angular time to compile
            
            # Check if server is running
            try:
                response = requests.get(f"http://localhost:{self.port}", timeout=5)
                if progress_callback:
                    progress_callback(1.0, "Deployment complete!")
                return True, f"http://localhost:{self.port}"
            except:
                # Server might still be starting
                if progress_callback:
                    progress_callback(0.9, "Waiting for server to start...")
                time.sleep(5)
                return True, f"http://localhost:{self.port}"
                
        except Exception as e:
            self.cleanup()
            raise e
    
    def cleanup(self):
        """Clean up resources"""
        try:
            # Terminate server process
            if self.server_process:
                if sys.platform == 'win32':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.server_process.pid)], 
                                 shell=True, capture_output=True)
                else:
                    self.server_process.terminate()
                    self.server_process.wait(timeout=5)
                self.server_process = None
            
            # Remove project directory
            if self.project_dir and os.path.exists(self.project_dir):
                shutil.rmtree(self.project_dir, ignore_errors=True)
                self.project_dir = None
                
        except Exception as e:
            st.error(f"Cleanup error: {str(e)}")

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
        zf.writestr("package.json", json.dumps(package, indent=2))
        
        # app.module.ts
        imports = ["import { NgModule } from '@angular/core';",
                  "import { BrowserModule } from '@angular/platform-browser';",
                  "import { FormsModule } from '@angular/forms';",
                  "import { AppComponent } from './app.component';"]
        declarations = ["AppComponent"]
        
        for comp in components:
            name = comp['name']
            imports.append(f"import {{ {name}Component }} from './{name.lower()}/{name.lower()}.component';")
            declarations.append(f"{name}Component")
        
        module = f"""{chr(10).join(imports)}

@NgModule({{
  declarations: [{', '.join(declarations)}],
  imports: [BrowserModule, FormsModule],
  bootstrap: [AppComponent]
}})
export class AppModule {{ }}"""
        
        zf.writestr("src/app/app.module.ts", module)
        
        # app.component with better styling
        app_ts = """import { Component } from '@angular/core';

@Component({
  selector: 'app-root',
  template: `
    <div class="app-container">
      <h1>🎨 Figma Generated Angular App</h1>
      <p class="subtitle">Your components are ready!</p>
      <div class="components">
        """ + '\n        '.join([f'<app-{c["name"].lower()}></app-{c["name"].lower()}>' for c in components]) + """
      </div>
    </div>
  `,
  styles: [`
    .app-container {
      min-height: 100vh;
      background: #f5f5f5;
      padding: 20px;
    }
    h1 {
      text-align: center;
      color: #3f51b5;
      margin-bottom: 10px;
    }
    .subtitle {
      text-align: center;
      color: #666;
      margin-bottom: 40px;
    }
    .components {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 20px;
      max-width: 1200px;
      margin: 0 auto;
    }
  `]
})
export class AppComponent {}"""
        
        zf.writestr("src/app/app.component.ts", app_ts)
        
        # main.ts
        zf.writestr("src/main.ts", """import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';
import { AppModule } from './app/app.module';

platformBrowserDynamic().bootstrapModule(AppModule)
  .catch(err => console.error(err));""")
        
        # index.html
        zf.writestr("src/index.html", """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Figma Angular App</title>
  <base href="/">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
  </style>
</head>
<body>
  <app-root></app-root>
</body>
</html>""")
        
        # angular.json with proper configuration
        angular_json = {
            "version": 1,
            "newProjectRoot": "projects",
            "projects": {
                "app": {
                    "projectType": "application",
                    "root": "",
                    "sourceRoot": "src",
                    "prefix": "app",
                    "architect": {
                        "build": {
                            "builder": "@angular-devkit/build-angular:browser",
                            "options": {
                                "outputPath": "dist/app",
                                "index": "src/index.html",
                                "main": "src/main.ts",
                                "polyfills": ["zone.js"],
                                "tsConfig": "tsconfig.json",
                                "assets": [],
                                "styles": [],
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
        zf.writestr("angular.json", json.dumps(angular_json, indent=2))
        
        # tsconfig.json
        tsconfig = {
            "compileOnSave": False,
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
        zf.writestr("tsconfig.json", json.dumps(tsconfig, indent=2))
        
        # README
        zf.writestr("README.md", f"""# Figma Generated App

## Install
```bash
npm install
```

## Run
```bash
ng serve
```

## Components
{chr(10).join(['- ' + c['name'] for c in components])}

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}
""")
    
    return buffer.getvalue()

def main():
    st.title("🎨 Figma to Angular Generator with Local Deployment")
    
    # Initialize session state
    if 'deployment_agent' not in st.session_state:
        st.session_state.deployment_agent = None
    if 'local_url' not in st.session_state:
        st.session_state.local_url = None
    
    # Sidebar
    with st.sidebar:
        st.header("Configuration")
        
        api_key = st.text_input("OpenAI Key (Optional)", type="password", value=os.getenv("OPENAI_API_KEY", ""))
        if api_key:
            openai.api_key = api_key
        
        method = st.radio("Input Method:", ["Figma API", "Upload Image"])
        
        st.divider()
        
        # Deployment status
        if st.session_state.local_url:
            st.success("🟢 App is running!")
            st.code(st.session_state.local_url)
            
            if st.button("🛑 Stop Server"):
                if st.session_state.deployment_agent:
                    st.session_state.deployment_agent.cleanup()
                    st.session_state.deployment_agent = None
                    st.session_state.local_url = None
                    st.info("Server stopped")
        
        # System check
        st.divider()
        st.subheader("System Check")
        
        deployment_agent = DeploymentAgent()
        
        if deployment_agent.check_node_installed():
            st.success("✅ Node.js installed")
        else:
            st.error("❌ Node.js not found")
            st.info("Install from: https://nodejs.org")
        
        if deployment_agent.check_angular_cli():
            st.success("✅ Angular CLI installed")
        else:
            st.warning("⚠️ Angular CLI not found")
            st.info("Will use npx to run Angular")
    
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
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📦 Generate & Download", disabled=not (token and file_key)):
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
                    st.download_button("💾 Download ZIP", zip_data, "figma-angular.zip", mime="application/zip")
                    
                    # Store zip data for deployment
                    st.session_state.zip_data = zip_data
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        with col2:
            if st.button("🚀 Generate & Deploy Locally", 
                        disabled=not (token and file_key) or not deployment_agent.check_node_installed(),
                        type="primary"):
                try:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    def update_progress(progress, message):
                        progress_bar.progress(progress)
                        status_text.text(message)
                    
                    # Generate
                    update_progress(0.1, "Connecting to Figma...")
                    agent = FigmaAgent(token)
                    file_data = agent.get_file(file_key)
                    components = agent.extract_components(file_data)
                    
                    if not components:
                        components = agent.create_sample_components()
                    
                    update_progress(0.2, "Generating Angular components...")
                    generator = CodeGenerator()
                    generated = [generator.generate_component(c) for c in components]
                    
                    zip_data = create_zip(generated)
                    
                    # Deploy
                    st.session_state.deployment_agent = DeploymentAgent()
                    success, url = st.session_state.deployment_agent.deploy(zip_data, update_progress)
                    
                    if success:
                        st.session_state.local_url = url
                        st.success(f"✅ App deployed successfully!")
                        st.balloons()
                        
                        # Show access info
                        st.info(f"🌐 Your app is running at: {url}")
                        st.info("📝 Note: First load may take a moment while Angular compiles")
                        
                        # Open in browser button
                        st.markdown(f"[🔗 Open in Browser]({url})")
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    if st.session_state.deployment_agent:
                        st.session_state.deployment_agent.cleanup()
                        st.session_state.deployment_agent = None
    
    else:
        st.header("Upload Design")
        
        file = st.file_uploader("Choose image", type=['png', 'jpg', 'jpeg'])
        
        if file:
            st.success(f"✅ File uploaded: {file.name}")
            st.info(f"📄 Size: {file.size // 1024} KB")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📦 Generate & Download"):
                    try:
                        with st.spinner("Generating..."):
                            agent = FigmaAgent()
                            components = agent.create_sample_components()
                            
                            generator = CodeGenerator()
                            generated = [generator.generate_component(c) for c in components]
                            
                            zip_data = create_zip(generated)
                        
                        st.success(f"✅ Generated {len(generated)} components!")
                        st.download_button("💾 Download ZIP", zip_data, "figma-angular.zip", mime="application/zip")
                        
                        # Store for deployment
                        st.session_state.zip_data = zip_data
                        
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
            
            with col2:
                if st.button("🚀 Generate & Deploy Locally", 
                           disabled=not deployment_agent.check_node_installed(),
                           type="primary"):
                    try:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        def update_progress(progress, message):
                            progress_bar.progress(progress)
                            status_text.text(message)
                        
                        # Generate
                        update_progress(0.1, "Generating components...")
                        agent = FigmaAgent()
                        components = agent.create_sample_components()
                        
                        generator = CodeGenerator()
                        generated = [generator.generate_component(c) for c in components]
                        
                        zip_data = create_zip(generated)
                        
                        # Deploy
                        st.session_state.deployment_agent = DeploymentAgent()
                        success, url = st.session_state.deployment_agent.deploy(zip_data, update_progress)
                        
                        if success:
                            st.session_state.local_url = url
                            st.success(f"✅ App deployed successfully!")
                            st.balloons()
                            
                            st.info(f"🌐 Your app is running at: {url}")
                            st.markdown(f"[🔗 Open in Browser]({url})")
                        
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                        if st.session_state.deployment_agent:
                            st.session_state.deployment_agent.cleanup()
                            st.session_state.deployment_agent = None

# Cleanup on exit
def cleanup_on_exit():
    if 'deployment_agent' in st.session_state and st.session_state.deployment_agent:
        st.session_state.deployment_agent.cleanup()

atexit.register(cleanup_on_exit)

if __name__ == "__main__":
    main()
