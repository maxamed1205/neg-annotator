# Small orchestrator executor implementing the steps from prompts/orchestrator.md
import json, yaml, glob, re, os

# 1) Read exactly one JSONL line: first non-empty
jl_path = os.path.join('data','annotations_step1.jsonl')
with open(jl_path, 'r', encoding='utf-8') as f:
    lines = [ln.strip() for ln in f if ln.strip()]
if not lines:
    print('''<<<TRACE_BEGIN\nERROR_NO_FILE: {}\n<<<TRACE_END\n{{"error":"NO_FILE","path":"{}"}}'''.format(jl_path, jl_path))
    raise SystemExit(0)
first = json.loads(lines[0])

text = first.get('text','')
item_id = first.get('id')
CUES = first.get('cues', [])

# 2) Load all YAML rules in rules/20_scopes in glob order
yaml_files = glob.glob('rules/20_scopes/**/*.yaml', recursive=True)
# keep order as returned
all_rules = []
for yf in yaml_files:
    with open(yf, 'r', encoding='utf-8') as fh:
        content = yaml.safe_load(fh)
    # content may be a list or dict
    if isinstance(content, dict) and 'rules' in content:
        rules_list = content['rules']
    elif isinstance(content, list):
        rules_list = content
    else:
        # single dict
        rules_list = [content]
    for idx, r in enumerate(rules_list, start=1):
        if r is None:
            continue
        r['_source_file'] = yf
        r['_index'] = idx
        all_rules.append(r)

# 3) List compact inventory grouped by group
inventory_by_group = {}
for r in all_rules:
    g = r.get('when_group') or r.get('group') or 'UNKNOWN'
    entry = {'id': r.get('id'), 'group': g, 'scope_strategy': r.get('scope_strategy') or r.get('action') or None, 'source_file': r['_source_file'], 'index': r['_index']}
    inventory_by_group.setdefault(g, []).append(entry)

# 4) For each cue, filter rules of same group and apply simple preconditions
candidates_per_cue = {}
choices_per_cue = {}
apply_results = {}
for cue in CUES:
    cue_label = cue.get('cue_label')
    cstart = cue.get('start')
    cend = cue.get('end')
    group = cue.get('group')
    # filter rules where when_group == group
    group_rules = [r for r in all_rules if (r.get('when_group')==group)]
    candidates = []
    for r in group_rules:
        rid = r.get('id')
        # check options.pattern -> include only if matches
        opts = r.get('options') or {}
        pattern = None
        if isinstance(opts, dict):
            pattern = opts.get('pattern')
        if pattern:
            try:
                flags = re.IGNORECASE if opts.get('case_insensitive') else 0
                if re.search(pattern, text, flags):
                    candidates.append(rid)
                else:
                    # pattern didn't match -> skip this rule
                    pass
                continue
            except re.error:
                # invalid pattern -> skip
                pass
        # check special cooccurrence requirement
        if isinstance(opts, dict) and opts.get('with_group'):
            need = opts.get('with_group')
            if any(c.get('group')==need for c in CUES):
                candidates.append(rid)
            else:
                pass
            continue
        # check guards deny_if_group_present
        guards = r.get('guards') or {}
        deny = guards.get('deny_if_group_present')
        if deny:
            # if any cue in sentence has that group and label
            dgroup = deny.get('group')
            dlabels = deny.get('labels') or []
            present = False
            for c in CUES:
                if c.get('group')==dgroup and (not dlabels or c.get('cue_label') in dlabels):
                    present = True
                    break
            if present:
                # disqualify
                continue
        # else include rule
        candidates.append(rid)
    candidates_per_cue[f"{cue_label}@[{cstart},{cend}]"] = candidates
    # 5) Select one rule: prefer rule with 'CORE' in id, else first
    sel = None
    if candidates:
        for cand in candidates:
            if 'CORE' in cand or 'G_CORE' in cand or cand.endswith('_CORE'):
                sel = cand
                break
        if not sel:
            sel = candidates[0]
    else:
        sel = 'AUCUNE_REGLE'
    choices_per_cue[f"{cue_label}@[{cstart},{cend}]"] = sel
    # 7) Apply selected rule if any
    if sel != 'AUCUNE_REGLE':
        # naive: return cue span as scope
        s = cstart
        e = cend
        scope_label = text[s:e]
        apply_results[f"{cue_label}@[{cstart},{cend}]"] = {'start': s, 'end': e, 'id': sel}
    else:
        apply_results[f"{cue_label}@[{cstart},{cend}]"] = None

# 6) RETRY not needed as all cues have choices
# Build TRACE
lines = []
lines.append('<<<TRACE_BEGIN')
# RÈGLES CHARGÉES
loaded = []
for r in all_rules:
    loaded.append(f"{r.get('id')}|{r.get('when_group') or r.get('group') or 'UNKNOWN'}|{r['_source_file']}/{r['_index']}")
lines.append('RÈGLES CHARGÉES (id, group, source_file/index): ' + ', '.join(loaded))
# CANDIDATS PAR CUE
for cue_key, candlist in candidates_per_cue.items():
    lines.append(f"CANDIDATS PAR CUE: cue={cue_key} → [{', '.join(candlist)}]")
# CHOIX PAR CUE
for cue_key, sel in choices_per_cue.items():
    lines.append(f"CHOIX PAR CUE: cue={cue_key} → {sel}")
# No retry
# APPLY lines
for cue_key, res in apply_results.items():
    if res:
        lines.append(f"APPLY: cue={cue_key} → span=[{res['start']},{res['end']}] id={res['id']}")

lines.append('<<<TRACE_END')
# Print trace
print('\n'.join(lines))
# After TRACE, print single JSON line
output = {
    'id': item_id,
    'text': text,
    'cues': CUES,
    'scopes': []
}
for cue_key, res in apply_results.items():
    if res:
        s = res['start']; e = res['end']
        scope_label = text[s:e]
        # find group from cue_key by matching
        # cue_key format "label@[s,e]"
        label = cue_key.split('@')[0]
        # find cue dict
        cue = next((c for c in CUES if c.get('cue_label')==label.strip()), None)
        group = cue.get('group') if cue else None
        output['scopes'].append({'id': res['id'], 'scope_label': scope_label, 'start': s, 'end': e, 'group': group})
# print single json line
print(json.dumps(output, ensure_ascii=False))
