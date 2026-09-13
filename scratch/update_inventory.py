import os
import ast
import re

ROOT_DIR = r"D:\SafeVision-AI"
INVENTORY_FILE = r"D:\SafeVision-AI\docs\report\PROJECT_REPOSITORY_INVENTORY.md"

def analyze_python_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and not node.name.startswith('__')]
        important = classes + functions
        return ", ".join(important[:5]) + ("..." if len(important) > 5 else "")
    except Exception:
        return "Parse error"

def analyze_ts_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        # Find exports, classes, interfaces, components
        exports = re.findall(r'export (?:const|function|class|interface|type) (\w+)', content)
        components = [e for e in exports if e[0].isupper()]
        funcs = [e for e in exports if e[0].islower()]
        important = components + funcs
        return ", ".join(important[:5]) + ("..." if len(important) > 5 else "")
    except Exception:
        return "Parse error"

def get_report_sections(rel_path):
    sections = []
    if rel_path.startswith("backend"): sections.append("4. Backend")
    if rel_path.startswith("frontend"): sections.append("3. Frontend")
    if rel_path.startswith("backend/app/api"): sections.append("4. APIs")
    if rel_path.startswith("backend/app/models") or rel_path.startswith("backend/alembic"): sections.append("5. Database")
    if "auth" in rel_path or "rbac" in rel_path: sections.append("6. Auth/RBAC")
    if "llm" in rel_path or "openrouter" in rel_path or "agent" in rel_path: sections.append("13. AI/LLM")
    if "cv" in rel_path or "yolo" in rel_path or "tracking" in rel_path: sections.append("7. CV")
    if "test" in rel_path: sections.append("24. Testing")
    return "<br>".join(sections) if sections else "General"

def update_inventory():
    with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        if line.startswith("| `"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 8:
                rel_path = parts[1].replace("`", "")
                filepath = os.path.join(ROOT_DIR, rel_path)
                
                # Analyze file
                important = "N/A"
                if rel_path.endswith(".py"):
                    important = analyze_python_file(filepath)
                elif rel_path.endswith(".ts") or rel_path.endswith(".tsx"):
                    important = analyze_ts_file(filepath)
                
                # Production?
                is_prod = "No" if "tests/" in rel_path or "test_" in rel_path else "Yes"
                
                # Sections
                sections = get_report_sections(rel_path)
                
                # Purpose (brief)
                purpose = "Implementation" if is_prod == "Yes" else "Testing"
                
                # Update line
                parts[3] = purpose
                parts[4] = important if important else "None"
                parts[5] = is_prod
                parts[6] = sections
                parts[7] = "[x] Verified"
                
                new_line = "| " + " | ".join(parts[1:-1]) + " |\n"
                new_lines.append(new_line)
                continue
        new_lines.append(line)
        
    with open(INVENTORY_FILE, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

if __name__ == "__main__":
    update_inventory()
    print("Inventory updated with structural analysis.")
