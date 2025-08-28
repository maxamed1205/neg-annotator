"""Debug script: pour chaque phrase de data/corpus_raw/example.txt
- charge les règles (10_markers)
- applique chaque règle via apply_marker_rule
- appelle detect_bipartite_cross_tokens
- appelle annotate_sentence pour comparaison
Usage:
    python tests/debug_markers.py        # itère sur toutes les phrases, appuyez sur Entrée entre chaque
    python tests/debug_markers.py 2      # ne teste que la phrase index 2 (1-based)
"""
from pathlib import Path
import sys
import json
import importlib.util

# Import runner.py as module (chemin relatif)
runner_path = Path(__file__).resolve().parents[1] / 'prompts' / 'runner.py'
spec = importlib.util.spec_from_file_location('runner', str(runner_path))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

RULES_DIR = Path(__file__).resolve().parents[1] / 'rules'
EXAMPLE_FILE = Path(__file__).resolve().parents[1] / 'data' / 'corpus_raw' / 'example.txt'


def pretty_print_cues(cues):
    if not cues:
        print("  (aucun cue détecté)")
        return
    for c in cues:
        print(f"  - id: {c.get('id')} | group: {c.get('group')} | label: '{c.get('cue_label')}' | span: ({c.get('start')},{c.get('end')})")


def main():
    # chargement des marqueurs
    markers = runner.load_markers(RULES_DIR)

    lines = [l for l in EXAMPLE_FILE.read_text(encoding='utf-8').splitlines() if l.strip()]
    if not lines:
        print(f"Fichier vide: {EXAMPLE_FILE}")
        return

    # optional index argument (1-based), optional --all to process all lines, and optional --pause
    idx = None
    pause = False
    process_all = False
    args = [a for a in sys.argv[1:]]
    if '--pause' in args:
        pause = True
        args.remove('--pause')
    if '--all' in args:
        process_all = True
        args.remove('--all')
    if args:
        try:
            idx = int(args[0]) - 1
        except Exception:
            idx = None

    # Default: process a single phrase (first line) unless --all or an index is provided
    if idx is not None and 0 <= idx < len(lines):
        to_test = [lines[idx]]
    elif process_all:
        to_test = lines
    else:
        to_test = [lines[0]]

    for i, sent in enumerate(to_test, start=(idx+1 if idx is not None else 1)):
        print("="*80)
        print(f"Phrase {i}: {sent}")
        print("- Appliquer les règles 10_markers (par groupe)")

        all_cues = []
        for g, rules in markers.items():
            print(f" Groupe: {g} ({len(rules)} règles)")
            for r in rules:
                found = runner.apply_marker_rule(r, sent)
                if found:
                    print(f"  Règle: {r.get('id')} ({r.get('cue_label')}) => {len(found)} hit(s)")
                    pretty_print_cues(found)
                    all_cues.extend(found)

        # Détecter bipartite cross tokens séparément (cas nécessaire)
        tokens = runner.tokenize_with_offsets(sent)
        bip_rule = None
        for r in markers.get('bipartite', []):
            if r.get('id') == 'NE_BIPARTITE_EXTENDED':
                bip_rule = r
                break
        if bip_rule:
            print('\n- detect_bipartite_cross_tokens (reconstruit ne ... pas séparés):')
            bip_cues = runner.detect_bipartite_cross_tokens(sent, tokens, all_cues, bip_rule)
            pretty_print_cues(bip_cues)
            all_cues.extend(bip_cues)

        # Déduplication basique
        uniq = {}
        for c in all_cues:
            key = (c.get('id'), c.get('group'), c.get('cue_label'), c.get('start'), c.get('end'))
            uniq[key] = c
        final_cues = list(uniq.values())

        print('\n- Cues agrégés (dédupliqués):')
        pretty_print_cues(final_cues)

        # Appel annotate_sentence pour comparaison complète (cues + scopes)
        print('\n- Résultat pipeline annotate_sentence (cues + scopes):')
        ann = runner.annotate_sentence(sent, i, markers, *runner.load_registry_and_scopes(RULES_DIR), mode='permissive')
        print(json.dumps({
            'cues': ann.get('cues'),
            'scopes': ann.get('scopes')
        }, ensure_ascii=False, indent=2))

        # Optionnel: pause entre phrases si demandé
        if pause and idx is None:
            input('\nAppuyez sur Entrée pour continuer...')


if __name__ == '__main__':
    main()
