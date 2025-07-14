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
import threading
import signal
import sys

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
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.figma.com/v1"
        self.headers = {"X-Figma-Token": self.access_token}
    
    def test_connection(self) -> bool:
        """Test if Figma token is valid"""
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
    
    def _classify_component(self, node: Dict) -> str:
        """Classify component type based on name and structure"""
        name = node.get('name', '').lower()
        
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
            st.error(f"OpenAI API error: {str(e)}")
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

class DeploymentAgent:
    """Agent responsible for building and deploying Angular app"""
    
    def __init__(self):
        self.project_path = None
        self.server_process = None
        self.port = None
    
    def create_angular_project(self, project_name: str, components: List[Dict]) -> str:
        """Create complete Angular project structure"""
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        self.project_path = os.path.join(temp_dir, project_name)
        os.makedirs(self.project_path, exist_ok=True)
        
        # Create package.json
        self._create_package_json()
        
        # Create Angular configuration files
        self._create_angular_config()
        
        # Create src directory structure
        self._create_src_structure()
        
        # Generate components
        for component in components:
            self._write_component_files(component)
        
        # Create app module
        self._create_app_module(components)
        
        # Create main app component
        self._create_app_component(components)
        
        return self.project_path
    
    def _create_package_json(self):
        """Create package.json file"""
        package_json = {
            "name": "figma-generated-app",
            "version": "1.0.0",
            "scripts": {
                "ng": "ng",
                "start": "ng serve",
                "build": "ng build",
                "serve": "ng serve --host 0.0.0.0 --port 4200"
            },
            "private": True,
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
        
        with open(os.path.join(self.project_path, 'package.json'), 'w') as f:
            json.dump(package_json, f, indent=2)
    
    def _create_angular_config(self):
        """Create Angular configuration files"""
        # angular.json
        angular_json = {
            "version": 1,
            "newProjectRoot": "projects",
            "projects": {
                "app": {
                    "projectType": "application",
                    "schematics": {},
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
                                "tsConfig": "tsconfig.app.json",
                                "assets": ["src/favicon.ico", "src/assets"],
                                "styles": [
                                    "@angular/material/prebuilt-themes/indigo-pink.css",
                                    "src/styles.css"
                                ],
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
        
        with open(os.path.join(self.project_path, 'angular.json'), 'w') as f:
            json.dump(angular_json, f, indent=2)
        
        # tsconfig.json
        tsconfig = {
            "compileOnSave": False,
            "compilerOptions": {
                "baseUrl": "./",
                "outDir": "./dist/out-tsc",
                "forceConsistentCasingInFileNames": True,
                "strict": True,
                "noImplicitOverride": True,
                "noPropertyAccessFromIndexSignature": True,
                "noImplicitReturns": True,
                "noFallthroughCasesInSwitch": True,
                "sourceMap": True,
                "declaration": False,
                "downlevelIteration": True,
                "experimentalDecorators": True,
                "moduleResolution": "node",
                "importHelpers": True,
                "target": "ES2022",
                "module": "ES2022",
                "useDefineForClassFields": False,
                "lib": ["ES2022", "dom"]
            }
        }
        
        with open(os.path.join(self.project_path, 'tsconfig.json'), 'w') as f:
            json.dump(tsconfig, f, indent=2)
        
        # tsconfig.app.json
        tsconfig_app = {
            "extends": "./tsconfig.json",
            "compilerOptions": {
                "outDir": "./out-tsc/app",
                "types": []
            },
            "files": ["src/main.ts"],
            "include": ["src/**/*.d.ts"]
        }
        
        with open(os.path.join(self.project_path, 'tsconfig.app.json'), 'w') as f:
            json.dump(tsconfig_app, f, indent=2)
    
    def _create_src_structure(self):
        """Create src directory structure"""
        src_path = os.path.join(self.project_path, 'src')
        app_path = os.path.join(src_path, 'app')
        
        os.makedirs(app_path, exist_ok=True)
        os.makedirs(os.path.join(src_path, 'assets'), exist_ok=True)
        
        # index.html
        index_html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Figma Generated App</title>
  <base href="/">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" type="image/x-icon" href="favicon.ico">
  <link rel="preconnect" href="https://fonts.gstatic.com">
  <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500&display=swap" rel="stylesheet">
  <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
</head>
<body class="mat-typography">
  <app-root></app-root>
</body>
</html>"""
        
        with open(os.path.join(src_path, 'index.html'), 'w') as f:
            f.write(index_html)
        
        # main.ts
        main_ts = """import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';
import { AppModule } from './app/app.module';

platformBrowserDynamic().bootstrapModule(AppModule)
  .catch(err => console.error(err));
"""
        
        with open(os.path.join(src_path, 'main.ts'), 'w') as f:
            f.write(main_ts)
        
        # styles.css
        styles_css = """@import "~@angular/material/prebuilt-themes/indigo-pink.css";

html, body { height: 100%; }
body { margin: 0; font-family: Roboto, "Helvetica Neue", sans-serif; }

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.component-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  margin-top: 20px;
}"""
        
        with open(os.path.join(src_path, 'styles.css'), 'w') as f:
            f.write(styles_css)
        
        # Create empty favicon.ico
        with open(os.path.join(src_path, 'favicon.ico'), 'wb') as f:
            f.write(b'')
    
    def _write_component_files(self, component: Dict):
        """Write component files to disk"""
        component_name = component['name'].lower()
        component_path = os.path.join(self.project_path, 'src', 'app', component_name)
        os.makedirs(component_path, exist_ok=True)
        
        # Write TypeScript file
        ts_file = os.path.join(component_path, f'{component_name}.component.ts')
        with open(ts_file, 'w') as f:
            f.write(component['typescript'])
        
        # Write HTML file
        html_file = os.path.join(component_path, f'{component_name}.component.html')
        with open(html_file, 'w') as f:
            f.write(component['html'])
        
        # Write CSS file
        css_file = os.path.join(component_path, f'{component_name}.component.css')
        with open(css_file, 'w') as f:
            f.write(component['css'])
    
    def _create_app_module(self, components: List[Dict]):
        """Create app.module.ts"""
        imports = [
            "import { NgModule } from '@angular/core';",
            "import { BrowserModule } from '@angular/platform-browser';",
            "import { BrowserAnimationsModule } from '@angular/platform-browser/animations';",
            "import { FormsModule } from '@angular/forms';",
            "",
            "// Angular Material imports",
            "import { MatButtonModule } from '@angular/material/button';",
            "import { MatCardModule } from '@angular/material/card';",
            "import { MatFormFieldModule } from '@angular/material/form-field';",
            "import { MatInputModule } from '@angular/material/input';",
            "import { MatToolbarModule } from '@angular/material/toolbar';",
            "import { MatIconModule } from '@angular/material/icon';",
            "import { MatListModule } from '@angular/material/list';",
            "",
            "// Components",
            "import { AppComponent } from './app.component';"
        ]
        
        declarations = ["AppComponent"]
        
        for component in components:
            name = component['name']
            imports.append(f"import {{ {name}Component }} from './{name.lower()}/{name.lower()}.component';")
            declarations.append(f"{name}Component")
        
        module_content = f"""{chr(10).join(imports)}

@NgModule({{
  declarations: [
    {',\n    '.join(declarations)}
  ],
  imports: [
    BrowserModule,
    BrowserAnimationsModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatToolbarModule,
    MatIconModule,
    MatListModule
  ],
  providers: [],
  bootstrap: [AppComponent]
}})
export class AppModule {{ }}"""
        
        module_path = os.path.join(self.project_path, 'src', 'app', 'app.module.ts')
        with open(module_path, 'w') as f:
            f.write(module_content)
    
    def _create_app_component(self, components: List[Dict]):
        """Create main app component"""
        app_path = os.path.join(self.project_path, 'src', 'app')
        
        # app.component.ts
        app_ts = """import { Component } from '@angular/core';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  title = 'Figma Generated Angular App';
  generatedAt = new Date();
}"""
        
        with open(os.path.join(app_path, 'app.component.ts'), 'w') as f:
            f.write(app_ts)
        
        # app.component.html
        component_tags = []
        for component in components:
            name = component['name']
            component_tags.append(f'    <app-{name.lower()} [data]="{{}}"></app-{name.lower()}>')
        
        app_html = f"""<mat-toolbar color="primary">
  <span>{{{{ title }}}}</span>
  <span class="spacer"></span>
  <span class="timestamp">Generated: {{{{ generatedAt | date:'short' }}}}</span>
</mat-toolbar>

<div class="container">
  <h1>Generated Components from Figma</h1>
  <p>These components were automatically generated from your Figma design using AI.</p>
  
  <div class="component-grid">
{chr(10).join(component_tags)}
  </div>
</div>"""
        
        with open(os.path.join(app_path, 'app.component.html'), 'w') as f:
            f.write(app_html)
        
        # app.component.css
        app_css = """.spacer {
  flex: 1 1 auto;
}

.timestamp {
  font-size: 14px;
  opacity: 0.8;
}

h1 {
  text-align: center;
  color: #3f51b5;
  margin: 30px 0 10px;
}

p {
  text-align: center;
  color: #666;
  margin-bottom: 30px;
}"""
        
        with open(os.path.join(app_path, 'app.component.css'), 'w') as f:
            f.write(app_css)
    
    def install_dependencies(self) -> bool:
        """Install npm dependencies"""
        try:
            # Check if npm exists
            npm_check = subprocess.run(['npm', '--version'], capture_output=True)
            if npm_check.returncode != 0:
                st.error("npm is not installed. Please install Node.js first.")
                return False
            
            # Run npm install
            process = subprocess.run(
                ['npm', 'install'],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            
            return process.returncode == 0
        except Exception as e:
            st.error(f"Error installing dependencies: {str(e)}")
            return False
    
    def start_dev_server(self) -> Tuple[bool, int]:
        """Start Angular development server"""
        try:
            # Find available port
            self.port = self._find_available_port()
            
            # Start ng serve
            self.server_process = subprocess.Popen(
                ['npm', 'run', 'serve', '--', '--port', str(self.port)],
                cwd=self.project_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for server to start
            time.sleep(15)  # Angular takes time to compile
            
            return True, self.port
        except Exception as e:
            st.error(f"Error starting server: {str(e)}")
            return False, 0
    
    def _find_available_port(self, start_port: int = 4200) -> int:
        """Find an available port"""
        port = start_port
        while port < 65535:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', port))
                    return port
            except:
                port += 1
        return 4200
    
    def stop_server(self):
        """Stop the development server"""
        if self.server_process:
            self.server_process.terminate()
            self.server_process = None

# Main Streamlit App
def main():
    st.title("🎨 Figma to Angular - AI Code Generator")
    st.markdown("Transform your Figma designs into Angular applications using AI")
    
    # Initialize session state
    if 'project_path' not in st.session_state:
        st.session_state.project_path = None
    if 'local_url' not in st.session_state:
        st.session_state.local_url = None
    if 'deployment_agent' not in st.session_state:
        st.session_state.deployment_agent = None
    
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
        
        # Cleanup
        if st.button("🧹 Clean Up", help="Stop server and clean temp files"):
            if st.session_state.deployment_agent:
                st.session_state.deployment_agent.stop_server()
            st.session_state.clear()
            st.success("Cleaned up!")
    
    # Main content
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
            "Valid URL": bool(file_key),
            "Node.js": subprocess.run(['node', '--version'], capture_output=True).returncode == 0
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
        
        # Progress tracking
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
                comp_progress = 40 + (30 * i / len(components))
                progress_bar.progress(int(comp_progress))
                status_text.text(f"Generating {component['name']}...")
                
                generated = code_agent.generate_angular_component(component)
                generated_components.append(generated)
            
            st.success(f"✅ Generated {len(generated_components)} components")
            
            # Step 4: Create Angular project
            status_text.text("📁 Creating Angular project...")
            progress_bar.progress(70)
            
            deployment_agent = DeploymentAgent()
            project_name = f"figma-app-{int(time.time())}"
            project_path = deployment_agent.create_angular_project(project_name, generated_components)
            
            st.session_state.project_path = project_path
            st.session_state.deployment_agent = deployment_agent
            
            # Step 5: Install dependencies
            status_text.text("📦 Installing dependencies...")
            progress_bar.progress(80)
            
            if deployment_agent.install_dependencies():
                st.success("✅ Dependencies installed")
            else:
                st.error("Failed to install dependencies")
                return
            
            # Step 6: Start dev server
            status_text.text("🚀 Starting development server...")
            progress_bar.progress(90)
            
            success, port = deployment_agent.start_dev_server()
            if success:
                local_url = f"http://localhost:{port}"
                st.session_state.local_url = local_url
                progress_bar.progress(100)
                status_text.text("✅ Complete!")
                
                # Success message
                st.balloons()
                st.success("🎉 Angular app generated and running!")
                
                # Display results
                st.divider()
                col1, col2 = st.columns(2)
                
                with col1:
                    st.header("🌐 Access Your App")
                    st.code(local_url)
                    st.markdown(f"[Open in Browser]({local_url})")
                
                with col2:
                    st.header("📂 Project Location")
                    st.code(project_path)
                    
                    if st.button("📋 Copy Path"):
                        st.code(project_path)
                
                # Show generated files
                with st.expander("View Generated Files"):
                    for comp in generated_components:
                        st.subheader(f"Component: {comp['name']}")
                        
                        tab1, tab2, tab3 = st.tabs(["TypeScript", "HTML", "CSS"])
                        
                        with tab1:
                            st.code(comp['typescript'], language='typescript')
                        with tab2:
                            st.code(comp['html'], language='html')
                        with tab3:
                            st.code(comp['css'], language='css')
            else:
                st.error("Failed to start development server")
                
        except Exception as e:
            st.error(f"Error: {str(e)}")
            progress_bar.progress(0)
            status_text.text("")
    
    # Display current status
    if st.session_state.local_url:
        st.divider()
        st.info(f"🟢 App is running at: {st.session_state.local_url}")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Refresh Status"):
                st.rerun()
        
        with col2:
            if st.button("🛑 Stop Server"):
                if st.session_state.deployment_agent:
                    st.session_state.deployment_agent.stop_server()
                    st.session_state.local_url = None
                    st.success("Server stopped")
        
        with col3:
            if st.button("📂 Open Project Folder"):
                if st.session_state.project_path:
                    webbrowser.open(st.session_state.project_path)

if __name__ == "__main__":
    main()
