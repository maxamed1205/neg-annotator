from pathlib import Path
import importlib.util
runner_path = Path(__file__).resolve().parents[1] / 'prompts' / 'runner.py'
spec = importlib.util.spec_from_file_location('runner', str(runner_path))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
lines = [l for l in Path('data/corpus_raw/example.txt').read_text(encoding='utf-8').splitlines() if l.strip()]
s = lines[1]
print('Sentence 2:', s)
print('\nTokens:')
for i,t in enumerate(runner.tokenize_with_offsets(s)):
    print(i, t)
# run detect_bipartite_cross_tokens
markers = runner.load_markers(Path('rules'))
for rule in markers.get('bipartite',[]):
    if rule.get('id')=='NE_BIPARTITE_EXTENDED':
        r=rule; break
print('\nNE_BIPARTITE_EXTENDED options:', r.get('options'))
print('\ndetect_bipartite_cross_tokens output:')
print(runner.detect_bipartite_cross_tokens(s, runner.tokenize_with_offsets(s), [], r))
