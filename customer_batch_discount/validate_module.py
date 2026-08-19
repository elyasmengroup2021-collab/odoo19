from pathlib import Path
import ast
import sys
import xml.etree.ElementTree as ET

root = Path('/home/ubuntu/customer_batch_discount')
errors = []

for path in sorted(root.rglob('*.py')):
    if path.name == 'validate_module.py':
        continue
    try:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        print(f'PYTHON OK: {path.relative_to(root)}')
    except Exception as exc:
        errors.append(f'PYTHON ERROR: {path}: {exc}')

for path in sorted(root.rglob('*.xml')):
    try:
        ET.parse(path)
        print(f'XML OK: {path.relative_to(root)}')
    except Exception as exc:
        errors.append(f'XML ERROR: {path}: {exc}')

manifest = root / '__manifest__.py'
try:
    manifest_data = ast.literal_eval(manifest.read_text(encoding='utf-8'))
    required = {'name', 'version', 'depends', 'data', 'installable'}
    missing = required - manifest_data.keys()
    if missing:
        errors.append(f'MANIFEST ERROR: missing keys {sorted(missing)}')
    else:
        print('MANIFEST OK')
    for rel in manifest_data.get('data', []):
        if not (root / rel).exists():
            errors.append(f'MANIFEST ERROR: missing data file {rel}')
except Exception as exc:
    errors.append(f'MANIFEST ERROR: {exc}')

if errors:
    print('\n'.join(errors), file=sys.stderr)
    raise SystemExit(1)
print('STATIC VALIDATION PASSED')
