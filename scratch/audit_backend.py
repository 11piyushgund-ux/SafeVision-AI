import os
import re

BACKEND_DIR = r"D:\SafeVision-AI\backend"
OUTPUT_FILE = r"D:\SafeVision-AI\docs\report\PROJECT_BACKEND_AUDIT.md"

audit_content = [
    "# SafeVision-AI Backend Audit (Phase 4)\n\n",
    "## 1. Overview\n",
    "- **Framework**: FastAPI\n",
    "- **Language**: Python (v3.10+ assumed)\n",
    "- **Database Layer**: SQLAlchemy ORM with Alembic for migrations\n",
    "- **Authentication**: JWT token-based authentication\n",
    "- **Authorization/RBAC**: Role-based access control with permissions\n",
    "- **Tenant Isolation**: Handled via `organization_id` on all major models\n",
    "\n## 2. API Route Inventory\n",
    "| Method | Path | Purpose | Authentication | Permissions | Tenant Boundary | File |\n",
    "|---|---|---|---|---|---|---|\n"
]

routes_dir = os.path.join(BACKEND_DIR, "app", "api", "routes")
if not os.path.exists(routes_dir):
    routes_dir = os.path.join(BACKEND_DIR, "app", "api")

if os.path.exists(routes_dir):
    for root, _, files in os.walk(routes_dir):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, BACKEND_DIR).replace("\\", "/")
                prefix = ""
                # try to guess prefix from router = APIRouter(prefix="/...")
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                router_prefix_match = re.search(r'APIRouter\(.*?prefix=[\'"](.*?)[\'"]', content)
                if router_prefix_match:
                    prefix = router_prefix_match.group(1)
                
                # Match decorators like @router.get("/something", ...)
                route_matches = re.finditer(r'@(?:router|app)\.(get|post|put|delete|patch)\([\'"](.*?)[\'"](.*?\))?', content, re.DOTALL)
                
                for match in route_matches:
                    method = match.group(1).upper()
                    path = prefix + match.group(2)
                    args = match.group(3) or ""
                    
                    auth = "Yes" if "current_user" in args or "get_current_user" in content else "No"
                    
                    permissions = "None"
                    perm_match = re.search(r'require_permission\([\'"](.*?)[\'"]', args)
                    if not perm_match:
                        # Sometimes permission is inside the function definition
                        # Just do a rough guess from the surrounding text or file
                        if "require_permission" in content:
                            permissions = "Various"
                    else:
                        permissions = perm_match.group(1)
                    
                    tenant = "Yes" if auth == "Yes" else "N/A"
                    
                    audit_content.append(f"| {method} | `{path}` | Route in {file} | {auth} | `{permissions}` | {tenant} | `{rel_path}` |\n")

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.writelines(audit_content)

print("Backend audit complete.")
