#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test spécifique pour detect_bipartite_cross_tokens."""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from prompts.runner import detect_bipartite_cross_tokens, tokenize_with_offsets

def test_cross_tokens():
    """Test de la fonction detect_bipartite_cross_tokens."""
    
    text = "Les patients n'ont pas présenté de complication postopératoire."
    tokens = tokenize_with_offsets(text)
    
    print(f"Texte: {text}")
    print("Tokens:")
    for i, (tok, start, end) in enumerate(tokens):
        print(f"  {i}: '{tok}' ({start}-{end})")
    
    # Règle simulée
    rule = {
        "id": "NE_BIPARTITE_EXTENDED",
        "group": "bipartite",
        "options": {
            "max_token_gap": 8,
            "exclude_verbs_from_cue": True
        }
    }
    
    # Tester la détection
    cues = detect_bipartite_cross_tokens(text, tokens, [], rule)
    
    print(f"\nCues détectés: {len(cues)}")
    for cue in cues:
        print(f"  Cue: '{cue['cue_label']}' (start: {cue['start']}, end: {cue['end']})")
        
        # Vérifier le span original
        span_text = text[cue['start']:cue['end']]
        print(f"  Span original: '{span_text}'")
        
        # Vérifier s'il y a des verbes dans le label
        if "ont" in cue['cue_label'] or "est" in cue['cue_label'] or "existe" in cue['cue_label']:
            print("  ❌ PROBLÈME: Verbe détecté dans le cue_label")
        else:
            print("  ✅ OK: Aucun verbe détecté dans le cue_label")

if __name__ == "__main__":
    test_cross_tokens()
