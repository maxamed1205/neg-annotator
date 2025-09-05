"""
Fonctions utilitaires pour corriger les positions des marqueurs de négation.
"""
import re
from typing import Tuple, List


def extract_negation_parts_with_positions(text: str, match, rule: dict) -> Tuple[str, int, int]:
    """
    Extrait les marqueurs de négation d'un match et calcule les positions correctes.
    
    Args:
        text: Le texte complet
        match: L'objet match regex
        rule: La règle appliquée
        
    Returns:
        Tuple[str, int, int]: (texte_nettoyé, position_début, position_fin)
    """
    match_text = match.group(0).strip()
    match_start = match.start()
    match_end = match.end()
    
    # Cas bipartite : "ne/n' ... pas/plus/jamais/etc"
    bipartite_pattern = r"(?:\bne\b|n['']).*?\b(pas|plus|jamais|rien|personne|guère|point|nul)\b"
    bipartite_match = re.search(bipartite_pattern, match_text, re.IGNORECASE)
    
    if bipartite_match:
        # Extraire les deux parties
        part1_pattern = r"(?:\bne\b|n[''])"
        part2_pattern = r"\b(pas|plus|jamais|rien|personne|guère|point|nul)\b"
        
        part1_match = re.search(part1_pattern, match_text, re.IGNORECASE)
        part2_match = re.search(part2_pattern, match_text, re.IGNORECASE)
        
        if part1_match and part2_match:
            # Nettoyer la première partie (ne garder que n' si c'est une contraction)
            part1_text = part1_match.group(0)
            if re.match(r"^n['']", part1_text, re.IGNORECASE):
                part1_text = re.match(r"^n['']", part1_text, re.IGNORECASE).group(0)
            
            part2_text = part2_match.group(0)
            cleaned_label = f"{part1_text} {part2_text}"
            
            # Calculer les positions dans le texte original
            part1_abs_start = match_start + part1_match.start()
            part1_abs_end = match_start + part1_match.end()
            part2_abs_start = match_start + part2_match.start()
            part2_abs_end = match_start + part2_match.end()
            
            # Pour les bipartites, on prend la position du début de part1
            # et on calcule la fin en fonction de la longueur du texte nettoyé
            new_start = part1_abs_start
            new_end = part1_abs_start + len(cleaned_label)
            
            return cleaned_label, new_start, new_end
    
    # Cas simple : un seul marqueur
    single_neg_patterns = [
        r"(?:\bne\b|n[''])",
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
    
    # Fallback : retourner le match original
    return match_text, match_start, match_end


def find_marker_positions_in_text(text: str, marker_text: str, approximate_start: int, window_size: int = 50) -> Tuple[int, int]:
    """
    Trouve les positions exactes d'un marqueur dans le texte original.
    
    Args:
        text: Le texte complet
        marker_text: Le texte du marqueur à localiser
        approximate_start: Position approximative de début
        window_size: Taille de la fenêtre de recherche
        
    Returns:
        Tuple[int, int]: (position_début, position_fin)
    """
    # Créer une fenêtre autour de la position approximative
    window_start = max(0, approximate_start - window_size)
    window_end = min(len(text), approximate_start + len(marker_text) + window_size)
    window = text[window_start:window_end]
    
    # Chercher le marqueur dans la fenêtre
    escaped_marker = re.escape(marker_text)
    match = re.search(escaped_marker, window, re.IGNORECASE)
    
    if match:
        real_start = window_start + match.start()
        real_end = window_start + match.end()
        return real_start, real_end
    else:
        # Fallback : utiliser la position approximative
        return approximate_start, approximate_start + len(marker_text)
