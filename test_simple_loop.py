#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Test simple de la logique de détection bipartite

def test_simple_loop():
    tokens = [('Les', 0, 3), ('patients', 4, 12), ('n', 13, 14), ("'", 14, 15), ('ont', 15, 18), ('pas', 19, 22)]
    
    print("Test de boucle simple:")
    for i, (tok, a, b) in enumerate(tokens):
        t = tok.lower()
        print(f"  Token {i}: '{tok}' ('{t}')")
        
        # Detection logic
        is_part1 = t == "ne" or t.startswith("n'") or t.startswith("n'")
        
        # Handle contraction "n" + "'"
        if t == "n" and i + 1 < len(tokens) and tokens[i + 1][0] in ["'", "'"]:
            is_part1 = True
            print(f"    Found contraction: n + {tokens[i + 1][0]}")
            
        print(f"    is_part1: {is_part1}")
        
        if is_part1:
            print(f"    Searching for part2 from token {i+1}...")
            part2_set = {"pas", "plus", "jamais", "rien", "personne", "guère", "point", "nul"}
            
            # Handle contraction case
            start_search = i + 2 if (t == "n" and i + 1 < len(tokens) and tokens[i + 1][0] in ["'", "'"]) else i + 1
            print(f"    start_search: {start_search}")
            
            for j in range(start_search, len(tokens)):
                t2, a2, b2 = tokens[j]
                print(f"      Checking token {j}: '{t2}'")
                if t2.lower() in part2_set:
                    print(f"      FOUND MATCH: '{t2}'")
                    # Would create cue here
                    break

if __name__ == "__main__":
    test_simple_loop()
