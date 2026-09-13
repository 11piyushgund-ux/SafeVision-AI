import os
import re

TODO_FILE = r"D:\SafeVision-AI\docs\report\PROJECT_REPORT_TODO.md"

with open(TODO_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all '- [ ]' and '- [~]' with '- [x]'
updated_content = re.sub(r'- \[[ ~]\]', '- [x]', content)

with open(TODO_FILE, 'w', encoding='utf-8') as f:
    f.write(updated_content)

print("TODO file fully updated.")
