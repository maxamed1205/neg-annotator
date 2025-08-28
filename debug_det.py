from pathlib import Path
import importlib.util
import re
from pprint import pprint

runner_path = Path(__file__).resolve().parents[1] / 'prompts' / 'runner.py'
spec = importlib.util.spec_from_file_location('runner', str(runner_path))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

RULES_DIR = Path(__file__).resolve().parents[1] / 'rules'
markers = runner.load_markers(RULES_DIR)
text = "Aucune anomalie n'a été trouvée, le bilan ne montre plus d'élévation enzymatique, et on n'a noté aucune rechute ni complication."

for r in markers.get('determinant', []):
    if r.get('id') == 'DET_NEG_GENERIQUE':
        print('Compiled pattern:', r.get('_clean_pattern'))
        pat = r.get('_compiled')
        print('Flags:', pat.flags)
        matches = list(pat.finditer(text))
        print('Matches found:', len(matches))
        for m in matches:
            print('  Match:', repr(m.group(0)), 'at', m.start(), m.end())
        break
