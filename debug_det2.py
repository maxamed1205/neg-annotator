from pathlib import Path
import importlib.util
import re

runner_path = Path(__file__).resolve().parent / 'prompts' / 'runner.py'
spec = importlib.util.spec_from_file_location('runner', str(runner_path))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

RULES_DIR = Path(__file__).resolve().parent / 'rules'
markers = runner.load_markers(RULES_DIR)
text = "Aucune anomalie n'a été trouvée, le bilan ne montre plus d'élévation enzymatique, et on n'a noté aucune rechute ni complication."

for r in markers.get('determinant', []):
    if r.get('id') == 'DET_NEG_GENERIQUE':
        print('Rule file:', r.get('_file'))
        print('Clean pattern:', repr(r.get('_clean_pattern')))
        pat = r.get('_compiled')
        print('Compiled flags:', pat.flags)
        matches = list(pat.finditer(text))
        print('Matches count:', len(matches))
        for m in matches:
            print('  Match text:', repr(m.group(0)), 'start-end:', m.start(), m.end())
            try:
                print('  groupdict:', m.groupdict())
            except:
                pass
            try:
                print('  groups:', m.groups())
            except:
                pass
        break
