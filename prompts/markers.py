from __future__ import annotations
import logging
import re
from typing import List, Dict, Any, Tuple, Optional
import inspect
import regex as reg
from .debug_print import debug_print

log = logging.getLogger("prompts.markers")

def _guard_hits(rule: Dict[str, Any], text: str, match=None) -> bool:
    guards = rule.get("_guards") or []
    if not guards:
        return False
    window = text
    if match:
        a = max(0, match.start() - 40)
        b = min(len(text), match.end() + 40)
        window = text[a:b]
    return any(g.search(window) for g in guards)


def _find_cleaned_text_positions(original_text: str, cleaned_text: str, approx_start: int, window_size: int = 50) -> List[Tuple[int, int]]:
    """
    Version corrigée pour trouver les positions exactes des segments nettoyés
    dans le texte original, sans remonter avant approx_start.
    """
    positions: List[Tuple[int, int]] = []
    current_start = approx_start

    for segment in cleaned_text.split():
        # Fenêtre de recherche uniquement à droite
        window_start = current_start
        window_end = min(len(original_text), current_start + len(segment) + window_size)
        window = original_text[window_start:window_end]

        # Normaliser les apostrophes pour la recherche
        normalized_segment = segment.replace("’", "'").replace("‘", "'")
        normalized_window = window.replace("’", "'").replace("‘", "'")

        # Chercher le segment dans la fenêtre
        escaped_segment = re.escape(normalized_segment)
        match = re.search(escaped_segment, normalized_window, re.IGNORECASE)

        if match:
            real_start = window_start + match.start()
            real_end = window_start + match.end()
        else:
            # Fallback plus souple (ignorer espaces multiples)
            flexible_pattern = re.escape(normalized_segment).replace(r'\\ ', r'\\s+')
            match = re.search(flexible_pattern, normalized_window, re.IGNORECASE)
            if match:
                real_start = window_start + match.start()
                real_end = window_start + match.end()
            else:
                # Dernier recours : utiliser position approximative
                real_start = current_start
                real_end = current_start + len(segment)

        # Éviter chevauchement avec segment précédent
        if positions and real_start < positions[-1][1]:
            real_start = positions[-1][1]
            real_end = max(real_end, real_start + len(segment))

        positions.append((real_start, real_end))
        current_start = real_end  # mettre à jour pour le segment suivant
    # print(f"[DEBUG _find_cleaned_text_positions] '{cleaned_text}' → {positions}")
    return positions

def _extract_negation_markers_only(text: str, match, rule: Dict[str, Any]) -> Tuple[str, int, int]:
    match_text = match.group(0)
    match_start = match.start()
    match_end = match.end()
    bipartite_pattern = r"(?:\bne\b|n['’]).*?\b(pas|plus|jamais|rien|personne|guère|point|nul)\b"
    bipartite_match = re.search(bipartite_pattern, match_text, re.IGNORECASE)
    if bipartite_match:
        part1_pattern = r"(?:\bne\b|n['’])"
        part2_pattern = r"\b(pas|plus|jamais|rien|personne|guère|point|nul)\b"
        part1_match = re.search(part1_pattern, match_text, re.IGNORECASE)
        part2_match = re.search(part2_pattern, match_text, re.IGNORECASE)
        if part1_match and part2_match:
            part1_text = part1_match.group(0)
            if re.match(r"^n['’]", part1_text, re.IGNORECASE):
                part1_text = re.match(r"^n['’]", part1_text, re.IGNORECASE).group(0)
            part2_text = part2_match.group(0)
            cleaned_label = f"{part1_text} {part2_text}"
            p1_start = match_start + part1_match.start()
            p1_end = match_start + part1_match.end()
            p2_start = match_start + part2_match.start()
            p2_end = match_start + part2_match.end()
            return cleaned_label, p1_start, p2_end
    single_neg_patterns = [
        r"(?:\bne\b|n['’])",
        r"\b(pas)\b",
        r"\b(plus)\b",
        r"\b(jamais)\b",
        r"\b(rien)\b",
        r"\b(personne)\b",
        r"\b(guère)\b",
        r"\b(point)\b",
        r"\b(nul)\b",
        r"\b(aucun|aucune)\b",
        r"\b(sans)\b",
        r"\b(ni)\b",
        r"\b(non)\b",
        r"\b(absence)\b",
    ]
    for pattern in single_neg_patterns:
        single_match = re.search(pattern, match_text, re.IGNORECASE)
        if single_match:
            particle_text = single_match.group(0)
            particle_start = match_start + single_match.start()
            particle_end = match_start + single_match.end()
            return particle_text, particle_start, particle_end
    return match_text, match_start, match_end


# deterministic surface markers
SURFACE_PREP_MARKERS = {
    "malgré": {"id": "PREP_MALGRÉ", "group": "preposition", "cue_label": "malgré"},
}

__all__ = ["apply_marker_rule", "inject_surface_markers", "_guard_hits"]
