from prompts import runner
from pathlib import Path
s = "Aucune anomalie n’a été trouvée, le bilan ne montre plus d'élévation enzymatique, et on n'a noté aucune rechute ni complication."
print('TEXT:\n', s)
print('\nTOKENS:')
for t,a,b in runner.tokenize_with_offsets(s):
    print(repr(t), a, b)
print('\nLOAD RULE:')
markers = runner.load_markers(Path('rules'))
for r in markers.get('bipartite', []):
    if r.get('id') == 'NE_BIPARTITE_EXTENDED':
        rule = r
        break
else:
    rule = None
print('Found rule:', bool(rule))
if rule:
    print('Rule options:', rule.get('options'))
    print('\nDETECT BIPARTITE:')
    res = runner.detect_bipartite_cross_tokens(s, runner.tokenize_with_offsets(s), [], rule)
    print(res)
else:
    print('NE_BIPARTITE_EXTENDED not found in rules')
