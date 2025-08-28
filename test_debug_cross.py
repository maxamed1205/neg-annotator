#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test avec debug pour detect_bipartite_cross_tokens."""

import sys
import os
import re
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from prompts.runner import tokenize_with_offsets, normalize_spaces

# Copie de la fonction avec debug
def debug_detect_bipartite_cross_tokens(text, tokens, existing_cues, rule):
    out = []
    max_tokens = rule.get("options", {}).get("max_token_gap")
    if not max_tokens:
        print("❌ Pas de max_token_gap défini")
        return out
    try:
        max_tokens = int(max_tokens)
    except Exception:
        max_tokens = 8
    
    print(f"✅ max_tokens: {max_tokens}")
    
    part1_set = {"ne", "n'", "n'"}
    part2_set = {"pas", "plus", "jamais", "rien", "personne", "guère", "point", "nul"}
    existing_keys = {(c.get("id"), c.get("start"), c.get("end")) for c in existing_cues}
    
    print(f"✅ part1_set: {part1_set}")
    print(f"✅ part2_set: {part2_set}")
    
    for i, (tok, a, b) in enumerate(tokens):
        t = tok.lower()
        print(f"\n--- Token {i}: '{tok}' ('{t}') ---")
        
        # un marqueur de début peut être "ne", ou bien un token débutant par "n'" ou "n'"
        # Gérer aussi les contractions séparées par le tokeniseur: "n" + "'"
        is_part1 = t == "ne" or t.startswith("n'") or t.startswith("n'")
        print(f"is_part1 initial: {is_part1}")
        
        # Gérer le cas où "n'" est tokenisé en "n" + "'"
        contraction_start = a
        contraction_token = tok
        if t == "n" and i + 1 < len(tokens) and tokens[i + 1][0] in ["'", "'"]:
            is_part1 = True
            contraction_token = "n'"  # Reconstruire la contraction
            contraction_start = a
            print(f"Contraction détectée: '{contraction_token}'")
            
        print(f"is_part1 final: {is_part1}")
        
        if is_part1:
            print(f"🔍 Recherche de part2 à partir du token {i+1}")
            gap = 0
            start_search = i + 2 if (t == "n" and i + 1 < len(tokens) and tokens[i + 1][0] in ["'", "'"]) else i + 1
            print(f"start_search: {start_search}")
            
            for j in range(start_search, len(tokens)):
                t2, a2, b2 = tokens[j]
                print(f"  Token {j}: '{t2}' -> gap {gap}")
                
                # ignore pure punctuation tokens
                PUNCT_RE = r"[,;:!?\.()\[\]{}«»""\"']"
                if re.match(PUNCT_RE, t2):
                    print(f"    Ponctuation ignorée")
                    continue
                gap += 1
                if gap > max_tokens:
                    print(f"    Gap trop grand ({gap} > {max_tokens})")
                    break
                    
                if t2.lower() in part2_set:
                    print(f"  ✅ Part2 trouvé: '{t2}'")
                    key = (rule.get("id"), contraction_start, b2)
                    if key not in existing_keys:
                        label = normalize_spaces(contraction_token + " " + t2)
                        print(f"  ✅ Cue créé: '{label}'")
                        
                        out.append({
                            "id": rule.get("id", "NE_BIPARTITE_EXTENDED"),
                            "cue_label": label,
                            "start": contraction_start,
                            "end": b2,
                            "group": rule.get("group", "bipartite")
                        })
                    else:
                        print(f"  ⚠️ Cue déjà existant")
                    break
                else:
                    print(f"    '{t2}' pas dans part2_set")
    
    return out

def test_debug():
    text = "Les patients n'ont pas présenté de complication postopératoire."
    tokens = tokenize_with_offsets(text)
    
    print(f"Texte: {text}")
    
    rule = {
        "id": "NE_BIPARTITE_EXTENDED",
        "group": "bipartite",
        "options": {
            "max_token_gap": 8,
            "exclude_verbs_from_cue": True
        }
    }
    
    cues = debug_detect_bipartite_cross_tokens(text, tokens, [], rule)
    
    print(f"\n=== RÉSULTAT ===")
    print(f"Cues détectés: {len(cues)}")
    for cue in cues:
        print(f"  Cue: '{cue['cue_label']}' (start: {cue['start']}, end: {cue['end']})")

if __name__ == "__main__":
    test_debug()
