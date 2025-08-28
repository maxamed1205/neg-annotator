from pathlib import Path
import importlib.util
runner_path = Path(__file__).resolve().parents[1] / 'prompts' / 'runner.py'
spec = importlib.util.spec_from_file_location('runner', str(runner_path))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

lines = [l for l in Path('data/corpus_raw/example.txt').read_text(encoding='utf-8').splitlines() if l.strip()]
s = lines[2]
print('SENTENCE:', s)
# tokens
tokens = runner.tokenize_with_offsets(s)
print('\nTOKENS:')
for i,t in enumerate(tokens):
    print(i, t)

# load markers and find NE_BIPARTITE_EXTENDED rule
markers = runner.load_markers(Path('rules'))
for r in markers.get('bipartite',[]):
    if r.get('id')=='NE_BIPARTITE_EXTENDED':
        rule = r
        break
else:
    rule=None
print('\nNE_BIPARTITE_EXTENDED rule options/max_token_gap=', rule.get('options'))

# call detect
res = runner.detect_bipartite_cross_tokens(s, tokens, [], rule)
print('\nDETECT OUTPUT:')
print(res)

# Also print tokens around potential n' and jamais
for i,(tok,a,b) in enumerate(tokens):
    if tok.lower().startswith("n"):
        print('\nFound token starting with n at', i, tok, a,b)
    if tok.lower().startswith('jamais'):
        print('\nFound token jamais at', i, tok, a,b)
