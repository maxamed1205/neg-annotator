#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from prompts.runner import *

def test_exclude_verbs():
    """Test si l'option exclude_verbs_from_cue fonctionne."""
    
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Simuler une règle avec exclude_verbs_from_cue
    rule = {
        "id": "NE_BIPARTITE_EXTENDED",
        "group": "bipartite",
        "options": {
            "exclude_verbs_from_cue": True,
            "max_token_gap": 8
        }
    }
    
    text = "Les patients n'ont pas présenté de complication postopératoire."
    tokens = tokenize_with_offsets(text)
    
    print(f"Tokens: {tokens}")
    print(f"Rule options: {rule.get('options')}")
    
    cues = detect_bipartite_cross_tokens(text, tokens, [], rule)
    
    print(f"Cues générés: {cues}")

if __name__ == "__main__":
    test_exclude_verbs()
