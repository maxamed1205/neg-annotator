import re
import regex as reg
from pathlib import Path
import yaml

# Load the bipartites YAML and extract the rule pattern
p = Path('rules/10_markers/bipartites.yaml')
items = yaml.safe_load(p.read_text(encoding='utf-8'))
pat_raw = None
for rule in items:
    if rule.get('id') == 'NE_COEXISTE_AVEC_DETERMINANT':
        pat_raw = rule.get('when_pattern')
        break
if not pat_raw:
    raise SystemExit('Rule not found')

# Current cleaning (as implemented now in load_markers)
clean_current = pat_raw.replace('\n', '')
clean_current = re.sub(r"(?<!\\)\\s+", '', clean_current)
clean_current = re.sub(r'\|', '|', clean_current)

# Proposed cleaning (conservative)
clean_proposed = pat_raw.replace('\n', ' ')
clean_proposed = re.sub(r'\s+', ' ', clean_proposed).strip()

# Compile both using regex (case-insensitive)
pat_current = reg.compile(clean_current, reg.IGNORECASE)
pat_proposed = reg.compile(clean_proposed, reg.IGNORECASE)

# Test sentence
s = "Les patients n'ont pas signalé de douleur, aucune fièvre n'a été observée, et il n'y a pas de signes cliniques; sans preuve d'infection."
# Use a simpler fragment where we expect the rule to apply
fragment = "il n'y a pas de signes cliniques"

print('RAW pattern:\n', pat_raw)
print('\nCLEAN (current):\n', clean_current)
print('\nCLEAN (proposed):\n', clean_proposed)

print('\nTesting against fragment:', fragment)
print('Current compiled pattern search ->', bool(pat_current.search(fragment)))
print('Proposed compiled pattern search ->', bool(pat_proposed.search(fragment)))

# Additionally, show exact match groups if any
m1 = pat_current.search(fragment)
if m1:
    print('\nCurrent MATCH groups:', m1.groups())
else:
    print('\nCurrent MATCH: None')

m2 = pat_proposed.search(fragment)
if m2:
    print('\nProposed MATCH groups:', m2.groups())
else:
    print('\nProposed MATCH: None')
