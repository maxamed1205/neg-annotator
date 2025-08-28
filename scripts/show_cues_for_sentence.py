from pathlib import Path
import json
import importlib.util
runner_path = Path(__file__).resolve().parents[1] / 'prompts' / 'runner.py'
spec = importlib.util.spec_from_file_location('runner', str(runner_path))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
RULES_DIR = Path('rules')
EXAMPLE_FILE = Path('data/corpus_raw/example.txt')
lines = [l for l in EXAMPLE_FILE.read_text(encoding='utf-8').splitlines() if l.strip()]
idx = 2  # 3rd sentence (0-based)
sent = lines[idx]
markers = runner.load_markers(RULES_DIR)
strategies, order_by_group = runner.load_registry_and_scopes(RULES_DIR)
# build strategies_by_id dict
strategies_by_id = strategies
res = runner.annotate_sentence(sent, idx+1, markers, strategies_by_id, order_by_group, mode='permissive')
print(json.dumps({'sentence': sent, 'cues': res.get('cues') if isinstance(res, dict) else res}, indent=2, ensure_ascii=False))
