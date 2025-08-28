#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append('.')

from prompts.runner import apply_marker_rule, _extract_negation_markers_only
import re

def test_debug_ne_pas_vs_n_pas():
    """Test pour diagnostiquer pourquoi n' devient ne dans les labels."""
    
    # Règle bipartite simulée
    rule = {
        "id": "NE_BIPARTITE_EXTENDED",
        "group": "bipartite",
        "when_pattern": r"(?:(?P<part2a>personne)\b\s+(?P<part1a>n['']?|ne)|(?P<part1b>n['']?|ne)\s*(?P<part2b>pas|plus|jamais|rien|personne|guère|point|nul)\b)",
        "cue_label": ["{part2a} {part1a}", "{part1b} {part2b}"],
        "options": {
            "regex": True,
            "exclude_verbs_from_cue": True
        },
        "_compiled": None
    }
    
    # Compiler la règle
    rule["_compiled"] = re.compile(rule["when_pattern"], re.IGNORECASE)
    
    text = "Les patients n'ont pas présenté de complication postopératoire."
    print(f"Texte: {text}")
    print(f"Marqueur attendu: 'n' pas'")
    print()
    
    # Test du regex match
    pattern = re.compile(rule["when_pattern"], re.IGNORECASE)
    matches = list(pattern.finditer(text))
    
    print("=== Analyse du regex match ===")
    for match in matches:
        print(f"Match complet: '{match.group(0)}'")
        print(f"Position: {match.start()}-{match.end()}")
        print(f"Groups: {match.groups()}")
        print(f"Groupdict: {match.groupdict()}")
        
        # Test de _extract_negation_markers_only
        print("\n=== Test _extract_negation_markers_only ===")
        cleaned_label, start_pos, end_pos = _extract_negation_markers_only(text, match, rule)
        print(f"Résultat: '{cleaned_label}' at {start_pos}-{end_pos}")
        print()
    
    # Test de apply_marker_rule
    print("=== Test apply_marker_rule ===")
    cues = apply_marker_rule(rule, text)
    for cue in cues:
        print(f"Cue généré: {cue}")
        print(f"Label: '{cue['cue_label']}'")
        print(f"Position: {cue['start']}-{cue['end']}")
        
        # Vérifier le texte extrait
        extracted_text = text[cue['start']:cue['end']]
        print(f"Texte extrait de la position: '{extracted_text}'")

if __name__ == "__main__":
    test_debug_ne_pas_vs_n_pas()
