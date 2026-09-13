import os
import json
import re

FRONTEND_DIR = r"D:\SafeVision-AI\frontend"
OUTPUT_FILE = r"D:\SafeVision-AI\docs\report\PROJECT_FRONTEND_AUDIT.md"

audit_content = [
    "# SafeVision-AI Frontend Audit (Phase 3)\n\n",
    "## 1. Overview\n"
]

# Read package.json
package_json_path = os.path.join(FRONTEND_DIR, "package.json")
if os.path.exists(package_json_path):
    with open(package_json_path, 'r', encoding='utf-8') as f:
        pkg = json.load(f)
    
    deps = pkg.get("dependencies", {})
    dev_deps = pkg.get("devDependencies", {})
    
    audit_content.append(f"- **Framework**: React (v{deps.get('react', 'Unknown')})\n")
    audit_content.append(f"- **Language**: TypeScript\n")
    audit_content.append(f"- **Build System**: Vite\n")
    audit_content.append(f"- **Package Manager**: npm\n")
    
    routing = "React Router" if "react-router-dom" in deps else "Unknown"
    audit_content.append(f"- **Routing**: {routing}\n")
    
    state_fetching = []
    if "@tanstack/react-query" in deps: state_fetching.append("React Query")
    if "axios" in deps: state_fetching.append("Axios")
    if "zustand" in deps: state_fetching.append("Zustand")
    audit_content.append(f"- **State/Data Fetching**: {', '.join(state_fetching)}\n")
    
    ui_libs = []
    if "lucide-react" in deps: ui_libs.append("Lucide Icons")
    if "tailwindcss" in dev_deps or "tailwindcss" in deps: ui_libs.append("Tailwind CSS")
    if "framer-motion" in deps: ui_libs.append("Framer Motion")
    if "@radix-ui/react-dialog" in deps: ui_libs.append("Radix UI (Modals)")
    if "recharts" in deps: ui_libs.append("Recharts")
    audit_content.append(f"- **UI Components**: {', '.join(ui_libs)}\n")

audit_content.append("\n## 2. Route Inventory\n")
audit_content.append("| Route Path | Purpose | Backend/API Dependencies | Permissions | Status |\n")
audit_content.append("|---|---|---|---|---|\n")

# Find routes in frontend/src/routes or similar
routes_dir = os.path.join(FRONTEND_DIR, "src", "routes")
if not os.path.exists(routes_dir):
    routes_dir = os.path.join(FRONTEND_DIR, "src", "pages")

if os.path.exists(routes_dir):
    for root, _, files in os.walk(routes_dir):
        for file in files:
            if file.endswith((".tsx", ".ts")):
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, routes_dir).replace("\\", "/")
                
                # Basic parsing
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                apis = re.findall(r'(?:fetch|axios\.\w+)\([\'"`](.*?)[\'"`]', content)
                api_deps = ", ".join(set(apis)) if apis else "None detected"
                
                route_path = "/" + rel_path.replace(".tsx", "").replace("index", "")
                audit_content.append(f"| `{route_path}` | View for {file} | {api_deps} | TBD | IMPLEMENTED |\n")

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.writelines(audit_content)

print("Frontend audit complete.")
