from pathlib import Path
import re
p = Path('data/corpus_raw/example.txt')
lines = [l for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
if len(lines) < 2:
    print('File has less than 2 lines')
    raise SystemExit(1)
s = lines[1]
print('SENTENCE:')
print(s)
print('\nOCCURRENCES:')
for m in re.finditer(r"\baucune\b", s, flags=re.IGNORECASE):
    print(repr(m.group(0)), m.start(), m.end(), 'context->', repr(s[max(0,m.start()-15):m.end()+15]))
