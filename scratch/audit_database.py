import os
import re

BACKEND_DIR = r"D:\SafeVision-AI\backend"
OUTPUT_FILE = r"D:\SafeVision-AI\docs\report\PROJECT_DATABASE_AUDIT.md"

audit_content = [
    "# SafeVision-AI Database Audit (Phase 5)\n\n",
    "## 1. Overview\n",
    "- **Database Engine**: PostgreSQL\n",
    "- **ORM**: SQLAlchemy\n",
    "- **Migrations**: Alembic\n\n",
    "## 2. Table Inventory\n",
    "| Model Class | Table Name | Key Columns/Types | Relationships | Tenant Isolation |\n",
    "|---|---|---|---|---|\n"
]

models_dir = os.path.join(BACKEND_DIR, "app", "models")
if os.path.exists(models_dir):
    for root, _, files in os.walk(models_dir):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                filepath = os.path.join(root, file)
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Match class ModelName(Base):
                class_matches = re.finditer(r'class (\w+)\(Base.*?\):', content)
                for class_match in class_matches:
                    model_name = class_match.group(1)
                    
                    # Find __tablename__
                    table_match = re.search(r'__tablename__\s*=\s*[\'"](.*?)[\'"]', content[class_match.end():])
                    table_name = table_match.group(1) if table_match else "Unknown"
                    
                    # Find columns
                    cols = re.findall(r'(\w+)\s*=\s*Column\((.*?)\)', content[class_match.end():])
                    col_info = []
                    for c_name, c_type in cols[:5]: # just top 5 to keep it readable
                        # simplify type
                        clean_type = c_type.split(",")[0].replace("String", "Str").replace("Integer", "Int")
                        col_info.append(f"{c_name}({clean_type})")
                    
                    # Check for JSON/JSONB
                    if "JSON" in content[class_match.end():]: col_info.append("... + JSON/JSONB")
                    
                    columns_str = ", ".join(col_info) if col_info else "TBD"
                    
                    # Relationships
                    rels = re.findall(r'(\w+)\s*=\s*relationship\([\'"](.*?)[\'"]', content[class_match.end():])
                    rels_str = ", ".join([f"{r[0]}->{r[1]}" for r in rels]) if rels else "None"
                    
                    tenant = "Yes (organization_id)" if "organization_id" in content[class_match.end():] else "No"
                    
                    audit_content.append(f"| `{model_name}` | `{table_name}` | {columns_str} | {rels_str} | {tenant} |\n")

audit_content.append("\n## 3. Migration History (Alembic)\n")
audit_content.append("| Revision | Purpose |\n")
audit_content.append("|---|---|\n")

migrations_dir = os.path.join(BACKEND_DIR, "alembic", "versions")
if os.path.exists(migrations_dir):
    for file in sorted(os.listdir(migrations_dir)):
        if file.endswith(".py"):
            filepath = os.path.join(migrations_dir, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # revision ID and message
            rev_match = re.search(r'revision\s*=\s*[\'"](.*?)[\'"]', content)
            msg_match = re.search(r'down_revision\s*=.*?#\s*(.*?)$', content, re.MULTILINE)
            # Actually down_revision isn't the message. Let's look for def upgrade(): docstring or comment
            rev = rev_match.group(1) if rev_match else file
            msg = file.replace(".py", "").replace("_", " ")
            audit_content.append(f"| `{rev}` | {msg} |\n")

with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.writelines(audit_content)

print("Database audit complete.")
