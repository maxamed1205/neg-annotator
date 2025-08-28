#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import re
import regex as reg
from pathlib import Path

# Ajouter le dossier prompts au path
sys.path.append(str(Path(__file__).parent / "prompts"))

from runner import load_markers, apply_marker_rule

def test_sentence():
    """Test la phrase problématique avec les règles"""
    
    # Phrase problématique
    text = "Aucun signe de récidive n'a été détecté à l'IRM."
    print(f"Phrase à tester: '{text}'")
    print("=" * 50)
    
    # Charger les règles
    print("Chargement des règles...")
    markers = load_markers(Path("rules"))
    
    # Tester les règles determinant
    print("\n--- Test règles DETERMINANT ---")
    det_rules = markers.get("determinant", [])
    print(f"Nombre de règles determinant: {len(det_rules)}")
    
    for rule in det_rules:
        print(f"\nTest règle: {rule.get('id')}")
        print(f"Pattern: {rule.get('when_pattern', 'NO_PATTERN')}")
        
        # Tester la règle
        cues = apply_marker_rule(rule, text)
        if cues:
            print(f"✓ MATCH trouvé: {cues}")
        else:
            print("✗ Aucun match")
            
            # Test manuel du pattern avec nettoyage
            pattern = rule.get('when_pattern')
            if pattern:
                try:
                    # Appliquer le même nettoyage que dans apply_marker_rule
                    clean_pattern = re.sub(r'\n\s*\|', '|', pattern)
                    clean_pattern = re.sub(r'\n\s+', '', clean_pattern)
                    
                    flags = reg.IGNORECASE if rule.get("options", {}).get("case_insensitive") else 0
                    compiled = reg.compile(clean_pattern, flags)
                    matches = list(compiled.finditer(text))
                    print(f"  Test manuel pattern nettoyé: {len(matches)} matches")
                    print(f"  Pattern nettoyé: {clean_pattern}")
                    for m in matches:
                        print(f"    Match: '{m.group()}' à position {m.start()}-{m.end()}")
                except Exception as e:
                    print(f"  Erreur compilation pattern: {e}")
    
    # Tester les règles bipartite
    print("\n--- Test règles BIPARTITE ---")
    bip_rules = markers.get("bipartite", [])
    print(f"Nombre de règles bipartite: {len(bip_rules)}")
    
    for rule in bip_rules:
        print(f"\nTest règle: {rule.get('id')}")
        print(f"Pattern: {rule.get('when_pattern', 'NO_PATTERN')}")
        
        # Tester la règle
        cues = apply_marker_rule(rule, text)
        if cues:
            print(f"✓ MATCH trouvé: {cues}")
        else:
            print("✗ Aucun match")
            
            # Test manuel du pattern
            pattern = rule.get('when_pattern')
            if pattern:
                try:
                    flags = reg.IGNORECASE if rule.get("options", {}).get("case_insensitive") else 0
                    compiled = reg.compile(pattern, flags)
                    matches = list(compiled.finditer(text))
                    print(f"  Test manuel pattern: {len(matches)} matches")
                    for m in matches:
                        print(f"    Match: '{m.group()}' à position {m.start()}-{m.end()}")
                except Exception as e:
                    print(f"  Erreur compilation pattern: {e}")

if __name__ == "__main__":
    test_sentence()
