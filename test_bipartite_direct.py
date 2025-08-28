#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importer les fonctions du runner
from prompts.runner import tokenize_with_offsets, detect_bipartite_cross_tokens

def test_bipartite_detection():
    text = "Les patients n'ont pas présenté de complication postopératoire."
    print(f"Texte: {text}")
    
    # Tokenizer
    tokens = tokenize_with_offsets(text)
    print(f"Tokens: {tokens}")
    
    # Test manuel de la logique
    for i, (tok, a, b) in enumerate(tokens):
        t = tok.lower()
        print(f"Token {i}: '{tok}' -> '{t}'")
        if t == "n":
            print(f"  Token 'n' trouvé à {i}")
            if i + 1 < len(tokens):
                next_tok = tokens[i + 1][0]
                print(f"  Token suivant: '{next_tok}'")
                if next_tok in ["'", "'"]:
                    print(f"  => Contraction détectée !")
    
    # Règle bipartite simplifiée
    rule = {
        "id": "TEST_BIPARTITE",
        "group": "bipartite",
        "part1": ["ne", "n'", "n'"],
        "part2": ["pas", "plus", "jamais"],
        "options": {"max_token_gap": 5},
        "exclude_verbs_from_cue": True
    }
    
    # Tester la détection
    print("Appelant detect_bipartite_cross_tokens...")
    cues = detect_bipartite_cross_tokens(text, tokens, [], rule)
    print(f"Fonction retournée, {len(cues)} cues trouvés")
    
    print("Cues détectés:")
    for cue in cues:
        print(f"  - {cue}")
        cue_text = text[cue['start']:cue['end']]
        print(f"    Texte original: '{cue_text}'")
        print(f"    Label généré: '{cue['cue_label']}'")

if __name__ == "__main__":
    test_bipartite_detection()
