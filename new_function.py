def detect_bipartite_cross_tokens(text: str, tokens: List[Tuple[str,int,int]], existing_cues: List[Dict[str,Any]], rule: Dict[str,Any]) -> List[Dict[str,Any]]:
    """
    Détecte les marqueurs bipartites de type « ne … pas » lorsque les deux
    éléments sont séparés par un ou plusieurs tokens. La logique est guidée par
    les options ``max_token_gap`` définies dans la règle YAML. Les listes des
    particules de départ (part1) et de fin (part2) sont dérivées du YAML
    (voir ``bipartites.yaml``) pour NE_BIPARTITE_EXTENDED.
    TOUJOURS exclut les verbes du label de cue (requis par l'utilisateur).

    :param text: la phrase brute
    :param tokens: liste des tokens avec offsets
    :param existing_cues: cues déjà détectés (pour éviter les doublons)
    :param rule: la règle YAML correspondante (doit contenir options.max_token_gap)
    :return: liste de nouvelles cues à ajouter
    """
    out = []
    # Only apply if the rule declares a max_token_gap; otherwise the standard regex suffira.
    max_tokens = rule.get("options", {}).get("max_token_gap")
    if not max_tokens:
        return out
    try:
        max_tokens = int(max_tokens)
    except Exception:
        max_tokens = 8
    # Hard‑code the list of possible second parts; these mirror the YAML definition.
    part1_set = {"ne", "n'", "n'"}
    part2_set = {"pas", "plus", "jamais", "rien", "personne", "guère", "point", "nul"}
    existing_keys = {(c.get("id"), c.get("start"), c.get("end")) for c in existing_cues}
    
    for i, (tok, a, b) in enumerate(tokens):
        t = tok.lower()
        # un marqueur de début peut être "ne", ou bien un token débutant par "n'" ou "n'"
        is_part1 = t == "ne" or t.startswith("n'") or t.startswith("n'")
        if is_part1:
            # Déterminer le token de contraction et ses positions
            if t == "ne":
                contraction_token = "ne"
                contraction_start = a
            else:
                # Pour les contractions comme "n'ont", garder seulement "n'"
                contraction_token = t[:2]  # "n'" or "n'"
                contraction_start = a
            
            # search ahead within max_tokens tokens (excluding punctuation tokens)
            gap = 0
            # Si c'est une contraction "n" + "'", commencer la recherche après l'apostrophe
            start_search = i + 2 if (t == "n" and i + 1 < len(tokens) and tokens[i + 1][0] in ["'", "'"]) else i + 1
            
            for j in range(start_search, len(tokens)):
                t2, a2, b2 = tokens[j]
                # ignore pure punctuation tokens (e.g., commas). We consider them as gap but don't count them.
                if re.match(PUNCT_RE, t2):
                    continue
                gap += 1
                if gap > max_tokens:
                    break
                if t2.lower() in part2_set:
                    # ensure we don't already have this cue
                    # Forme la clé avec les vraies positions 
                    key = (rule.get("id"), contraction_start, b2)
                    if key not in existing_keys:
                        # TOUJOURS exclure les verbes pour les bipartites (requis par l'utilisateur)
                        # Créer un label avec seulement les particules de négation
                        label = normalize_spaces(contraction_token + " " + t2)
                        # Pour les positions, utiliser le span complet mais le label ne contient que les particules
                        cue_start = contraction_start  # Start of "ne/n'"
                        cue_end = b2   # End of "pas/plus/etc" (full span for scope calculation)
                        
                        out.append({
                            "id": rule.get("id", "NE_BIPARTITE_EXTENDED"),
                            "cue_label": label,
                            "start": cue_start,
                            "end": cue_end,
                            "group": rule.get("group", "bipartite")
                        })
                    break
    return out
