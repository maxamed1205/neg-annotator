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
                # Use same cleaning logic as runner.py
                clean = re.sub(r'\n\s*\|', '|', pat)
                clean = re.sub(r'\n\s+', '', clean)
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
                    try:
                        gp = mm.groups()
                    except Exception:
                        gp = ()
                    print(f"{rid}: when_pattern -> MATCH '{mm.group(0)}' at {mm.start()}-{mm.end()} groups_named={gd} groups_pos={gp}")
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
                    try:
                        gp = mm.groups()
                    except Exception:
                        gp = ()
                    print(f"{rid}: when_pattern -> MATCH '{mm.group(0)}' at {mm.start()}-{mm.end()} groups={gd} (no cue produced)")

print('\nAll rules inspected.')

# Collect ALL matches (literal markers and when_pattern matches) and print labels ordered by position
print('\n--- All matches (labels) collected from rules ---')
all_matches = []
for g, rules in markers.items():
    for r in rules:
        rid = r.get('id')
        wm = r.get('when_marker')
        compiled = r.get('_compiled')
        raw_pat = r.get('when_pattern')
        try:
            if wm:
                for m in re.finditer(rf"\b{re.escape(wm)}\b", sent, flags=re.IGNORECASE):
                    lbl = wm
                    all_matches.append((m.start(), lbl, rid))
            else:
                pat = compiled
                if not pat and raw_pat:
                    clean = re.sub(r'\n\s*\|', '|', raw_pat)
                    clean = re.sub(r'\n\s+', '', clean)
                    pat = re.compile(clean, re.IGNORECASE)
                if pat:
                    for m in pat.finditer(sent):
                        # prefer named groups if present
                        gd = {}
                        try:
                            gd = m.groupdict()
                        except Exception:
                            gd = {}
                        if gd:
                            vals = [v for v in gd.values() if v]
                            lbl = ' '.join(vals).strip()
                        else:
                            lbl = m.group(0).strip()
                        all_matches.append((m.start(), lbl, rid))
        except Exception:
            continue

# Sort by position and print labels joined by ' | '
all_matches.sort(key=lambda x: x[0])
labels = [t[1] for t in all_matches if t[1]]
print('Labels (all matches): ' + ' | '.join(labels))

# Print final produced cues (unique_cues from apply_marker_rule path would be used in runner; we replicate ordering)
print('\n--- Final produced cues (combined: apply_marker_rule + bipartite token-based + surface injections) ---')
# Start from cues produced by apply_marker_rule for all rules
cues = []
for r in all_rules:
    try:
        produced = runner.apply_marker_rule(r, sent)
    except Exception:
        produced = []
    cues.extend(produced)

# Add bipartite token-based detections (NE_BIPARTITE_EXTENDED) similar to annotate_sentence
if 'bipartite' in markers:
    for r in markers.get('bipartite', []):
        if r.get('id') == 'NE_BIPARTITE_EXTENDED':
            toks = runner.tokenize_with_offsets(sent)
            bip = runner.detect_bipartite_cross_tokens(sent, toks, cues, r)
            if bip:
                for c in bip:
                    print(f"{r.get('id')}: detect_bipartite_cross_tokens -> '{c.get('cue_label')}' at {c.get('start')}-{c.get('end')} group={c.get('group')}")
            cues.extend(bip)
            break

# Inject deterministic surface markers (e.g. 'malgré') if missing
cues = runner.inject_surface_markers(sent, cues)

# Deduplicate cues the same way as in runner.annotate_sentence
unique_cues = {}
for c in cues:
    key = (c.get('id'), c.get('group'), c.get('cue_label'), c.get('start'), c.get('end'))
    if key not in unique_cues:
        unique_cues[key] = c
cues = list(unique_cues.values())

final_cues = [(c.get('start', 0), c.get('cue_label', ''), c.get('end', -1), c.get('group')) for c in cues]
final_cues.sort(key=lambda x: x[0])
print('Final Labels: ' + ' | '.join([f"{c[1]} {c[0]}-{c[2]}" for c in final_cues if c[1]]))

# Print non-QC matches only (to avoid noisy QC entries)
print('\n--- Non-QC pattern matches (ordered) ---')
non_qc = [m for m in all_matches if not str(m[2]).upper().startswith('QC_')]
non_qc.sort(key=lambda x: x[0])
print('Non-QC Labels: ' + ' | '.join([m[1] for m in non_qc if m[1]]))

print('\n--- Raw matches (pos, label, rule_id) ---')
for t in all_matches:
    print(t)