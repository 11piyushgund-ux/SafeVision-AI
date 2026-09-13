import sys

file_path = r'D:\SafeVision-AI\frontend\src\lib\api-types.ts'

with open(file_path, 'rb') as f:
    content = f.read()

idx = content.rfind(b'export type DocumentKind')

if idx != -1:
    clean_content = content[:idx].decode('utf-8')
    clean_content += 'export type DocumentKind = "policy" | "sop";\n\n'
    clean_content += '// ==============================================================================\n'
    clean_content += '// Rules (from schemas/rule_schema.py)\n'
    clean_content += '// ==============================================================================\n\n'
    clean_content += 'export interface ControlsResponse {\n'
    clean_content += '  ignored_classes: string[];\n'
    clean_content += '  restricted_area_enabled: boolean;\n'
    clean_content += '}\n\n'
    clean_content += 'export interface DetectionFilterUpdate {\n'
    clean_content += '  ignored_classes: string[];\n'
    clean_content += '}\n\n'
    clean_content += 'export interface RestrictedAreaUpdate {\n'
    clean_content += '  enabled: boolean;\n'
    clean_content += '}\n'
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(clean_content)
    print('Fixed file.')
else:
    print('Could not find DocumentKind marker.')
