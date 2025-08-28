#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import regex as reg
from typing import Tuple, List, Dict, Any

def test_exclude_verbs_from_cue():
    """Test the exclusion of verbs from bipartite negation cues."""
    
    test_cases = [
        "Les patients n'ont pas présenté de complication postopératoire.",
        "Cette méthode n'est pas considérée comme une alternative fiable.",
        "Il n'existe pas de preuve scientifique soutenant cette hypothèse.",
        "Le patient ne se plaint guère.",
        "Personne ne vient."
    ]
    
    # Pattern from the YAML rule - test simpler patterns
    patterns_to_test = [
        r"\bn['']?\b",  # Just ne/n'
        r"\bpas\b",     # Just pas
        r"\bn['']?\s+\w+\s+pas\b",  # ne + word + pas
        r"\bn['']?\w*\s+pas\b"      # ne + verb + pas
    ]
    
    for i, pattern in enumerate(patterns_to_test):
        print(f"\n=== Pattern {i+1}: {pattern} ===")
        compiled_pattern = reg.compile(pattern, reg.IGNORECASE)
        
        for text in test_cases[:3]:  # Test only first 3 cases
            print(f"\nTexte: {text}")
            
            for match in compiled_pattern.finditer(text):
                print(f"  Match: '{match.group(0)}' ({match.start()}-{match.end()})")

def extract_negation_markers_only(text: str, match) -> Tuple[str, int, int]:
    """
    Extract only negation markers from a match, excluding verbs.
    """
    
    # Get all named groups from the match
    groups = match.groupdict()
    
    # Handle "Personne ne" case (inverted)
    if groups.get('part2a') and groups.get('part1a'):
        part2a = groups['part2a']
        part1a = groups['part1a']
        
        # Find positions of each part
        part2a_start = text.find(part2a, match.start())
        part2a_end = part2a_start + len(part2a)
        
        part1a_start = text.find(part1a, part2a_end)
        part1a_end = part1a_start + len(part1a)
        
        combined_label = f"{part2a} {part1a}"
        return combined_label, part2a_start, part1a_end
    
    # Handle standard "ne ... pas" case
    elif groups.get('part1b') and groups.get('part2b'):
        part1b = groups['part1b']
        part2b = groups['part2b']
        
        # Find positions of each part
        part1b_start = text.find(part1b, match.start())
        part1b_end = part1b_start + len(part1b)
        
        part2b_start = text.find(part2b, part1b_end)
        part2b_end = part2b_start + len(part2b)
        
        combined_label = f"{part1b} {part2b}"
        return combined_label, part1b_start, part2b_end
    
    # Fallback: return original match
    return match.group(0), match.start(), match.end()

if __name__ == "__main__":
    test_exclude_verbs_from_cue()
