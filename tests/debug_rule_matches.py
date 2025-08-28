"""Vérifie, pour une phrase donnée, quelles règles 10_markers ont un pattern et si elles matchent.
Usage:
    python tests/debug_rule_matches.py 1
"""
from pathlib import Path
import importlib.util
import sys
import re

runner_path = Path(__file__).resolve().parents[1] / 'prompts' / 'runner.py'
spec = importlib.util.spec_from_file_location('runner', str(runner_path))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

RULES_DIR = Path(__file__).resolve().parents[1] / 'rules'
EXAMPLE_FILE = Path(__file__).resolve().parents[1] / 'data' / 'corpus_raw' / 'example.txt'

lines = [l for l in EXAMPLE_FILE.read_text(encoding='utf-8').splitlines() if l.strip()]
if not lines:
    print('Fichier vide')
    sys.exit(1)

idx = 0
if len(sys.argv) > 1:
    try:
        idx = int(sys.argv[1]) - 1
    except Exception:
        idx = 0
sent = lines[idx]
print('Phrase:', sent)

markers = runner.load_markers(RULES_DIR)

# Check candidate groups
groups = ['bipartite','determinant','preposition','locution','lexical','conjonction']

for g in groups:
    print('\n=== Groupe', g, '===')
    for r in markers.get(g,[]):
        rid = r.get('id')
        pat = r.get('when_pattern')
        wm = r.get('when_marker')
        if not pat and not wm:
            print(f"{rid}: (no when_pattern/when_marker)")
            continue
        # Use compiled pattern if available
        compiled = r.get('_compiled')
        if not compiled and pat:
            # try to clean/compile similar to loader
            try:
                clean = pat.replace('\n','')
                # also remove unnecessary spaces between tokens for visual
                clean = re.sub(r'(?<!\\)\s+', '', clean)
                compiled = re.compile(clean, re.IGNORECASE)
            except Exception as e:
                compiled = None
        if wm:
            # simple literal marker search - list all occurrences (only when present)
            matches = list(re.finditer(rf"\b{re.escape(wm)}\b", sent, flags=re.IGNORECASE))
            if matches:
                for mm in matches:
                    print(f"{rid}: when_marker='{wm}' -> MATCH '{mm.group(0)}' at {mm.start()}-{mm.end()}")
        elif compiled:
            # list all matches with offsets (only when present)
            matches = list(compiled.finditer(sent))
            if matches:
                for mm in matches:
                    # try to show group0/full match and groupdict if any
                    gd = ''
                    try:
                        gd = mm.groupdict()
                    except Exception:
                        gd = {}
                    print(f"{rid}: when_pattern -> MATCH '{mm.group(0)}' at {mm.start()}-{mm.end()} groups={gd}")
        else:
            print(f"{rid}: pattern present but not compilable")

# Also inspect detect_bipartite_cross_tokens output
print('\n--- detect_bipartite_cross_tokens output ---')
if 'bipartite' in markers:
    for r in markers['bipartite']:
        if r.get('id') == 'NE_BIPARTITE_EXTENDED':
            toks = runner.tokenize_with_offsets(sent)
            bip = runner.detect_bipartite_cross_tokens(sent, toks, [], r)
            print(bip)
            break

print('\nDone')


print('\n--- cues produced by apply_marker_rule (per rule) ---')
all_rules = [r for L in markers.values() for r in L]
for r in all_rules:
    rid = r.get('id')
    try:
        produced = runner.apply_marker_rule(r, sent)
    except Exception as e:
        print(f"{rid}: apply_marker_rule raised {e}")
        produced = []
    if produced:
        for c in produced:
            print(f"{rid}: PRODUCED cue -> '{c.get('cue_label')}' at {c.get('start')}-{c.get('end')} group={c.get('group')}")
    else:
        # If no cues produced, only show matches if present (QC or action rules)
        pat = r.get('_compiled')
        wm = r.get('when_marker')
        if wm:
            matches = list(re.finditer(rf"\b{re.escape(wm)}\b", sent, flags=re.IGNORECASE))
            if matches:
                for mm in matches:
                    print(f"{rid}: when_marker='{wm}' -> MATCH '{mm.group(0)}' at {mm.start()}-{mm.end()} (no cue produced)")
        elif pat:
            matches = list(pat.finditer(sent))
            if matches:
                for mm in matches:
                    try:
                        gd = mm.groupdict()
                    except Exception:
                        gd = {}
                    print(f"{rid}: when_pattern -> MATCH '{mm.group(0)}' at {mm.start()}-{mm.end()} groups={gd} (no cue produced)")

print('\nAll rules inspected.')
