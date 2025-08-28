#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test direct pour l'exclusion des verbes."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from prompts.runner import apply_marker_rule
import re

def test_direct_verb_exclusion():
    """Test direct de l'exclusion des verbes."""
    
    # Simulation d'une règle bipartite
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
    
    # Compiler le pattern
    flags = re.IGNORECASE
    clean_pattern = rule["when_pattern"]
    rule["_compiled"] = re.compile(clean_pattern, flags)
    
    # Texte de test
    text = "Les patients n'ont pas présenté de complication postopératoire."
    
    print(f"Texte: {text}")
    print(f"Règle: {rule['id']} (group: {rule['group']})")
    print(f"Pattern: {rule['when_pattern']}")
    
    # Appliquer la règle
    cues = apply_marker_rule(rule, text)
    
    for cue in cues:
        print(f"Cue généré: '{cue['cue_label']}' (start: {cue['start']}, end: {cue['end']})")
        
        # Vérifier s'il y a des verbes
        if "ont" in cue['cue_label'] or "est" in cue['cue_label'] or "existe" in cue['cue_label']:
            print("❌ PROBLÈME: Verbe détecté dans le cue")
        else:
            print("✅ OK: Aucun verbe détecté")

if __name__ == "__main__":
    test_direct_verb_exclusion()
