#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test pour vérifier l'exclusion des verbes dans les cues."""

import json

def check_verb_exclusion():
    """Vérifie si les verbes sont exclus des cues dans les annotations."""
    
    with open("data/annotations_step1.jsonl", "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            data = json.loads(line.strip())
            text = data["text"]
            cues = data["cues"]
            
            print(f"\n--- Phrase {line_num} ---")
            print(f"Texte: {text}")
            
            for cue in cues:
                cue_label = cue["cue_label"]
                cue_id = cue["id"]
                group = cue["group"]
                
                print(f"Cue: '{cue_label}' (id: {cue_id}, group: {group})")
                
                # Check for verbs in bipartite cues
                if group == "bipartite":
                    # Verbs that should be excluded
                    excluded_verbs = ["ont", "est", "était", "sont", "existe", "était", "a", "ai", "as", "avez", "avons", "avaient"]
                    
                    found_verbs = []
                    for verb in excluded_verbs:
                        if verb in cue_label.lower():
                            found_verbs.append(verb)
                    
                    if found_verbs:
                        print(f"  ❌ PROBLÈME: Verbes trouvés dans le cue: {found_verbs}")
                    else:
                        print(f"  ✅ OK: Aucun verbe détecté")
                        
            print()

if __name__ == "__main__":
    check_verb_exclusion()
