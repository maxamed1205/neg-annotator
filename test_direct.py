#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

# Ajouter le dossier prompts au path
sys.path.append(str(Path(__file__).parent / "prompts"))

from runner import load_markers, apply_marker_rule

def test_direct():
    """Test direct de la fonction apply_marker_rule"""
    
    text = "Aucun signe de récidive n'a été détecté à l'IRM."
    print(f"Phrase: '{text}'")
    print("=" * 50)
    
    # Charger les règles avec patterns nettoyés
    markers = load_markers(Path("rules"))
    
    print("\n--- Test règle DET_NEG_GENERIQUE ---")
    det_rules = markers.get("determinant", [])
    
    for rule in det_rules:
        if rule.get("id") == "DET_NEG_GENERIQUE":
            print(f"Règle: {rule.get('id')}")
            print(f"Pattern original: {rule.get('when_pattern', 'NO_PATTERN')}")
            print(f"Pattern nettoyé: {rule.get('_clean_pattern', 'NOT_CLEANED')}")
            print(f"Pattern compilé: {rule.get('_compiled')}")
            
            # Test direct avec apply_marker_rule
            print("\n--- Test apply_marker_rule ---")
            cues = apply_marker_rule(rule, text)
            print(f"Résultat: {cues}")
            
            if cues:
                print("✓ SUCCESS - Cues détectés!")
                for cue in cues:
                    print(f"  Cue: {cue}")
            else:
                print("✗ ÉCHEC - Aucun cue détecté")
            
            break
    else:
        print("Règle DET_NEG_GENERIQUE non trouvée!")

if __name__ == "__main__":
    test_direct()
