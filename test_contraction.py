#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test direct pour vérifier la préservation des formes contractées."""

import re
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from prompts.runner import _extract_negation_markers_only

def test_contraction_preservation():
    """Test direct de la préservation des contractions."""
    
    test_cases = [
        ("n'ont pas", "n' pas"),  # Devrait donner "n' pas"
        ("n'existe pas", "n' pas"),  # Devrait donner "n' pas"
        ("n'est pas", "n' pas"),  # Devrait donner "n' pas"
        ("ne montrent", "ne"),  # Devrait donner "ne"
    ]
    
    for input_text, expected in test_cases:
        print(f"\nTest: '{input_text}' -> Attendu: '{expected}'")
        
        # Créer un match fictif
        class FakeMatch:
            def __init__(self, text):
                self.text = text
                self.start_pos = 0
                self.end_pos = len(text)
            
            def group(self, n=0):
                return self.text
            
            def start(self):
                return self.start_pos
            
            def end(self):
                return self.end_pos
        
        fake_match = FakeMatch(input_text)
        
        # Appliquer la fonction
        result_text, start, end = _extract_negation_markers_only("", fake_match, {})
        
        print(f"Résultat: '{result_text}'")
        
        if result_text == expected:
            print("✅ OK")
        else:
            print(f"❌ ERREUR: Attendu '{expected}', obtenu '{result_text}'")

if __name__ == "__main__":
    test_contraction_preservation()
