import yaml
import re
from pathlib import Path

p = Path('rules/10_markers/bipartites.yaml')
raw = p.read_text(encoding='utf-8')
items = yaml.safe_load(raw)

# find rule
for rule in items:
    if rule.get('id') == 'NE_COEXISTE_AVEC_DETERMINANT':
        pat = rule.get('when_pattern')
        print('RAW when_pattern:')
        print(pat)
        # current cleaning (from runner.load_markers)
        clean_current = pat.replace('\n', '')
        clean_current = re.sub(r"(?<!\\)\\s+", '', clean_current)
        clean_current = re.sub(r'\|', '|', clean_current)
        print('\nCLEAN (current, buggy):')
        print(clean_current)
        # proposed cleaning
        clean_proposed = pat.replace('\n', ' ')
        clean_proposed = re.sub(r'\s+', ' ', clean_proposed).strip()
        print('\nCLEAN (proposed):')
        print(clean_proposed)
        break
else:
    print('Rule not found')
