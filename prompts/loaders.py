from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Any, Tuple
import re
import yaml
import regex as reg
import logging
log = logging.getLogger("prompts.loaders")
import inspect

debug_mode = True  # active/désactive les prints de debug

# Dictionnaire global pour suivre combien de fois chaque message a été affiché
_debug_counters = {}

def debug_print(msg: str, *args, max_print: int = None, **kwargs):
    """
    Affiche un message de debug avec informations sur l'appelant.
    max_print : nombre maximum d'affichages pour ce message (None = illimité)
    """
    if not debug_mode:
        return

    # Compteur pour ce message
    counter_key = msg
    if counter_key not in _debug_counters:
        _debug_counters[counter_key] = 0

    if max_print is not None and _debug_counters[counter_key] >= max_print:
        return  # on dépasse le nombre de prints autorisé pour ce message

    _debug_counters[counter_key] += 1

    # Info sur l'appelant
    frame = inspect.currentframe().f_back
    func_name = frame.f_code.co_name
    line_no = frame.f_lineno
    filename = frame.f_code.co_filename.split("\\")[-1]

    # Préparer le message principal
    output = f"[DEBUG] {filename}:{func_name}:{line_no} → {msg}"

    # Ajouter les variables avec leur type
    if args:
        vars_info = ", ".join(f"{repr(a)} (type={type(a).__name__})" for a in args)
        output += " | Vars: " + vars_info

    print(output, **kwargs)

def _debug_return(p: Path) -> Path:
    debug_print(f"Fichier trouvé : {p.name}")  # print le debug
    return p  # retourne le Path pour la comprehension


def _iter_yaml_files(folder: Path) -> List[Path]: # Parcourt le dossier donné et retourne une liste de tous les fichiers YAML valides (Path objects)
    return sorted([  
        # _debug_return(p)  # appelle debug_print puis retourne p
        p for p in folder.glob("*.yaml")    # Cherche tous les fichiers dont le nom se termine par .yaml dans le dossier et ajoute les à la liste
        # if p.is_file()                    # Garde seulement ceux qui sont de vrais fichiers (pas des dossiers)
        if not  p.name.startswith("_")      # Ignore les fichiers dont le nom commence par "_" (souvent des fichiers internes)  # Dans une list comprehension, le `if` sert à filtrer les éléments et ne nécessite pas de `:`
])  # Trie la liste des noms de fichiers par ordre alphabétique et la retourne


def infer_group_from_filename(name: str) -> str:
    n = name.lower()
    if "ni" in n or "conjonction" in n:
        return "conjonction"
    if "ne_pas" in n or "bipartites" in n or "ne_" in n:
        return "bipartite"
    if "preposition" in n or "sans" in n or "prep" in n:
        return "preposition"
    if "det" in n or "aucun" in n or "determinant" in n or "pas_de" in n:
        return "determinant"
    if "locution" in n:
        return "locution"
    if "lexical" in n:
        return "lexical"
    if "adversative" in n or "mais" in n:
        return "adversative"
    return "autres_marqueurs"



def load_markers(rules_dir: Path):
    d = rules_dir / "10_markers"  # dossier contenant les fichiers YAML de règles
    grouped = {}  # dictionnaire des règles regroupées par type
    print_count = 0  # compteur local pour ce fichier
    MAX_PRINTS = 2  # nombre de prints maximum par fichier
    for f in _iter_yaml_files(d):  # itère sur chaque fichier YAML valide
        # debug_print(f"Traitement du fichier YAML : {f.name}")  # <-- ajout
        items = yaml.safe_load(f.read_text(encoding="utf-8")) # Lit le fichier YAML et convertit son contenu en objets Python (ici, une liste où chaque élément est une règle)
        # print(type(items))  
        print(f"[DEBUG] Fichier {f.name} chargé, type={type(items).__name__}, nombre d'éléments={len(items) if isinstance(items, list) else 'N/A'}")
        # debug_print(f"Chargé {len(items) if isinstance(items, list) else 0} items depuis le fichier : {f.name}")
        if not isinstance(items, list):
            continue
        for rule in items:
            rule["_file"] = str(f) # Dans la liste on va charger chaque règle et ajouter le chemin du fichier pour traçabilité
            # debug_print(f"Règle chargée depuis {f.name} : {rule}")
            gid = rule.get("group") or infer_group_from_filename(f.name)
            # debug_print(f"Assignation du groupe gid='{gid}' pour la règle: id='{rule.get('id', 'N/A')}'")
            rule["group"] = gid
            # if print_count < MAX_PRINTS:
                # debug_print(f"Règle complète chargée : {rule}")
                # print_count += 1
            pat = rule.get("when_pattern")                                # Récupère le motif regex brut défini dans la règle
            if pat:                                                       # Si un motif regex est présent
                clean_pattern = pat.replace('\n', ' ')                    # Remplace les sauts de ligne par des espaces
                clean_pattern = reg.sub(r'#[^|]+(?=\|)', '', clean_pattern)  # Supprime les commentaires avant un "|"
                clean_pattern = reg.sub(r'#[^)]+(?=\))', '', clean_pattern)  # Supprime les commentaires avant une ")"
                clean_pattern = reg.sub(r'\s+', ' ', clean_pattern).strip()  # Réduit tous les espaces multiples et supprime les espaces de début/fin
                clean_pattern = reg.sub(r'\s*\|\s*', '|', clean_pattern)     # Nettoie les séparateurs "|" en supprimant les espaces autour
                clean_pattern = reg.sub(r'\(\s+', '(', clean_pattern)         # Supprime l'espace après "("
                clean_pattern = reg.sub(r'\s+\)', ')', clean_pattern)         # Supprime l'espace avant ")"
                clean_pattern = reg.sub(r'>\s+', '>', clean_pattern)          # Supprime l'espace après ">"
                flags = reg.IGNORECASE if rule.get("options", {}).get("case_insensitive") else 0  # Ignore la casse si demandé
                flags |= reg.VERBOSE                                         # Permet les commentaires et espaces dans la regex
                rule["_compiled"] = reg.compile(pat, flags)                  # Compile le motif original et l'ajoute à la règle
                rule["_clean_pattern"] = clean_pattern                       # Stocke le motif nettoyé pour affichage ou debug

            comp_guards = []                                                # Liste des regex de garde négatives compilées
            for g in rule.get("negative_guards", []) or []:                 # Parcourt les gardes éventuelles
                gp = g.get("pattern") if isinstance(g, dict) else g         # Récupère le motif brut si c'est un dict ou la valeur directement
                if gp:
                    comp_guards.append(reg.compile(gp, reg.IGNORECASE))     # Compile chaque garde avec insensibilité à la casse
            if comp_guards:
                rule["_guards"] = comp_guards                                # Ajoute les gardes compilées à la règle
            grouped.setdefault(gid, []).append(rule)                        # Ajoute la règle dans son groupe correspondant
    # for g, L in grouped.items():
        # debug_print(f"Markers '{g}': {len(L)} règles")

    # Retourne le dictionnaire `grouped` qui contient toutes les règles chargées depuis les fichiers YAML.
    # Chaque clé est un identifiant de groupe (`gid`) et chaque valeur est une liste de dictionnaires, 
    # où chaque dictionnaire représente une règle. 
    # Chaque règle inclut ses champs d'origine (id, when_pattern, cue_label, etc.) ainsi que :
    #   - "_file" : chemin complet du fichier YAML d'origine (str)
    #   - "group" : le groupe auquel la règle appartient (str)
    #   - "_compiled" : motif regex compilé avec reg.compile (re.Pattern), si applicable
    #   - "_clean_pattern" : motif regex nettoyé (str), pour debug ou affichage
    #   - "_guards" : liste de regex compilées correspondant aux negative_guards, si présentes
    # Type du retour : Dict[str, List[Dict[str, Any]]]
    # for gid, rules in grouped.items():
        # debug_print(f"Groupe '{gid}' contient {len(rules)} règles", max_print=1)
        # Affiche la première règle et son type pour confirmation
        # if rules:
            # debug_print(f"Exemple de règle dans le groupe '{gid}': {rules[0]}", 
                        # f"Type={type(rules[0]).__name__}", max_print=1)
    return grouped


def load_registry_and_scopes(rules_dir: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[str]]]:
    dir20 = rules_dir / "20_scopes"
    reg_path = dir20 / "_registry.yaml"
    order_by_group: Dict[str, List[str]] = {}
    if reg_path.exists():
        raw = yaml.safe_load(reg_path.read_text(encoding="utf-8"))
        routes = raw.get("routes_by_group", raw)
        for g, cfg in routes.items():
            if isinstance(cfg, dict) and "strategies" in cfg:
                order_by_group[g] = list(cfg["strategies"])
            elif isinstance(cfg, list):
                order_by_group[g] = list(cfg)
    strategies: Dict[str, Dict[str, Any]] = {}
    for f in _iter_yaml_files(dir20) + [p for p in dir20.glob("*.yaml") if p.is_file() and not p.name.startswith("_")]:
        try:
            items = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(items, list):
            continue
        for s in items:
            sid = s.get("id");
            if not sid: continue
            s["_file"] = str(f)
            strategies[sid] = s
    log.info("Stratégies chargées: %d", len(strategies))
    for g, L in order_by_group.items():
        log.info("Ordre '%s': %s", g, ", ".join(L))
    return strategies, order_by_group


__all__ = ["_iter_yaml_files", "infer_group_from_filename", "load_markers", "load_registry_and_scopes"]
