import os

ROOT_DIR = r"D:\SafeVision-AI"
OUTPUT_FILE = r"D:\SafeVision-AI\docs\report\PROJECT_REPOSITORY_INVENTORY.md"

EXCLUDE_DIRS = {
    ".git", 
    "node_modules", 
    ".venv", 
    "__pycache__", 
    "dist", 
    "build", 
    ".next", 
    "out", 
    ".pytest_cache",
    "docs" # Exclude docs directory to avoid circular inclusion
}

# The user instructed not to modify the BACKUP
EXCLUDE_PREFIXES = [
    "D:\\SafeVision-AI_BACKUP_PHASE10B",
    "D:/SafeVision-AI_BACKUP_PHASE10B"
]

RELEVANT_EXTENSIONS = {
    ".py", ".tsx", ".ts", ".js", ".json", ".yaml", ".yml", 
    ".sql", ".md", ".txt", ".lock", ".toml", ".env", ".env.example"
}

inventory = [
    "# SafeVision-AI Project Repository Inventory\n",
    "## Excluded Directories\n",
    "The following directories were intentionally skipped as they contain generated, vendor, or cache files:\n",
    "- `.git`: Version control history\n",
    "- `node_modules`: Frontend dependencies\n",
    "- `.venv`: Python virtual environment\n",
    "- `__pycache__`: Python bytecode caches\n",
    "- `.pytest_cache`: Test caches\n",
    "- `dist` / `build` / `.next` / `out`: Frontend build output\n",
    "- `docs`: The generated documentation itself\n",
    "- `D:\\SafeVision-AI_BACKUP_PHASE10B`: Backup directory\n\n",
    "## Inventory\n",
    "| Path | Category | Purpose | Important Classes/Functions | Contributes to Prod? | Report Sections | Status |\n",
    "|------|----------|---------|-----------------------------|-----------------------|-----------------|--------|\n"
]

files_counted = 0

for dirpath, dirnames, filenames in os.walk(ROOT_DIR):
    # Filter out excluded directories
    dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not any(os.path.join(dirpath, d).startswith(prefix) for prefix in EXCLUDE_PREFIXES)]
    
    for filename in filenames:
        ext = os.path.splitext(filename)[1].lower()
        if ext in RELEVANT_EXTENSIONS or filename in ("Dockerfile", "docker-compose.yml", "requirements.txt", "package.json"):
            filepath = os.path.join(dirpath, filename)
            # Make path relative to ROOT_DIR
            rel_path = os.path.relpath(filepath, ROOT_DIR)
            rel_path = rel_path.replace("\\", "/") # use forward slashes
            
            if rel_path.startswith("docs/"):
                continue

            category = "Unknown"
            if rel_path.startswith("backend/app/api"): category = "API Route"
            elif rel_path.startswith("backend/app/services"): category = "Backend Service"
            elif rel_path.startswith("backend/app/models"): category = "Database Model"
            elif rel_path.startswith("backend/app/schemas"): category = "Pydantic Schema"
            elif rel_path.startswith("backend/alembic"): category = "Migration"
            elif rel_path.startswith("backend/tests"): category = "Test"
            elif rel_path.startswith("frontend/src/routes") or rel_path.startswith("frontend/src/pages"): category = "Frontend Route"
            elif rel_path.startswith("frontend/src/components"): category = "Frontend Component"
            elif rel_path.startswith("frontend/src/lib") or rel_path.startswith("frontend/src/services"): category = "Frontend Utility/Service"
            elif filename == "package.json" or filename == "requirements.txt" or filename == "poetry.lock": category = "Dependency Manifest"
            elif ext == ".md": category = "Documentation"
            elif ext in (".yaml", ".yml", ".json", ".env"): category = "Configuration"

            inventory.append(f"| `{rel_path}` | {category} | TBD | TBD | TBD | TBD | [ ] Not inspected |\n")
            files_counted += 1

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.writelines(inventory)

print(f"Inventory created with {files_counted} files.")
