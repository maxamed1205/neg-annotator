from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from .types import Token, Cue, Rule, Strategy
from .tokenize import tokenize_with_offsets, window_right, strip_leading_de, normalize_spaces, DEFAULT_STOP_PUNCT, DEFAULT_STOP_LEXEMES
from .loaders import _iter_yaml_files, infer_group_from_filename, load_markers, load_registry_and_scopes
from .markers import _guard_hits, _format_cue_label, _extract_negation_markers_only, _find_cleaned_text_positions
import regex as reg
from .bipartite import detect_bipartite_cross_tokens
from .strategies import exec_strategy
from .qc import dedup, apply_qc
import os
import yaml
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

def _mk_cue(rule: Dict[str,Any], a:int,b:int, span:str) -> Dict[str,Any]:
    return {"id": rule.get("id","UNK_RULE"), "cue_label": span, "start": a, "end": b, "group": rule.get("group","unknown")}

seen_starts = set()

def apply_marker_rule(rule: Dict[str,Any], text: str, seen_intervals: List[Tuple[int, int]]) -> List[Dict[str,Any]]:
    out: List[Dict[str,Any]] = []
    if rule.get("action") or str(rule.get("id",""))[:2].upper() == "QC": # Ignorer certaines règles
        return out
    pat = rule.get("_compiled") # Récupère le motif regex précompilé (pattern original `when_pattern`, compilé dans load_markers avec reg.VERBOSE + options éventuelles).
    # debug_print("Motif précompilé récupéré", pat)  # Affiche le pattern compilé et son type
    if not pat:
        return out
    # Parcourt tout le texte à la recherche de correspondances avec la regex compilée `pat`.
    # Retourne un itérable (iterator) de `re.Match` objects, chacun contenant :
    #   - la sous-chaîne correspondante (`match.group()`)
    #   - la position de début (`match.start()`)
    #   - la position de fin (`match.end()`)
    # Type : Iterator[re.Match]
    # liste intermédiaire pour stocker les intervalles des matches conservés
# ensemble pour stocker les positions de début déjà vues
    for m in pat.finditer(text):  # parcourt tout le texte et trouve chaque portion (mot, phrase, ou expression) qui correspond au motif regex compilé dans 'pat'
        start, end = m.start(), m.end()
        # debug_print("Match avant filtrage :", m.group(0), "| Positions:", (start, end), "| Groupdict:", m.groupdict())
        # ignorer si ce match chevauche un intervalle déjà vu
        if any(start == s for s, e in seen_intervals):
            # debug_print("Match ignoré (début identique à un match existant):", m.group(0), "| Positions:", (start, end))
            continue

        # sinon, on conserve ce match
        seen_intervals.append((start, end))
        # debug_print("Match unique conservé:", m.group(0), "| Positions:", (start, end), "| Groupdict:", m.groupdict())

        if _guard_hits(rule, text, m):
            continue
        # Vérifier exclusion des verbes
        exclude_verbs = rule.get("options", {}).get("exclude_verbs_from_cue", False)
        # nettoyer le span si nécessaire
        if exclude_verbs:
            # debug_print("Avant extract", m.group(0), "start", m.start(), "end", m.end())
            span_text, start_pos, end_pos = _extract_negation_markers_only(text, m, rule)
            # Recalculer les positions nettoyées
        cleaned_positions = _find_cleaned_text_positions(text, span_text, start_pos)

        # générer le label
        if exclude_verbs:
            label = span_text
        else:
            label = _format_cue_label(rule.get("cue_label"), m)
        # Construire le cue avec positions découpées
        cue = {
            "id": rule.get("id", "UNK_RULE"),
            "cue_label": normalize_spaces(label if label else span_text),
            "positions": cleaned_positions,  # liste de tuples (start, end)
            "group": rule.get("group", "unknown"),
        }
        out.append(cue)
    return out



# --- Additional deterministic helpers (surface prep injection) ---
# Note: bipartite detection and deterministic surface marker injection are
# implemented in dedicated modules. See prompts.bipartite and prompts.markers.


def build_candidates_rules_id_cues(groups_present: List[str], markers_by_group: Dict[str,List[Dict[str,Any]]]) -> List[Dict[str,Any]]:
    out=[]
    for g in groups_present:
        out.append({"group": g, "rules": [r.get("id","UNK_RULE") for r in markers_by_group.get(g,[])]})
    return out


debug_mode = True  # Global toggle for debug printing

def annotate_sentence(text: str, sid: int, markers_by_group, strategies_by_id, order_by_group, seen_intervals) -> Dict[str,Any]:
    tokens = tokenize_with_offsets(text)
    cues: List[Dict[str,Any]] = []

    for g, rules in markers_by_group.items(): # Parcourt chaque groupe (g) par exemple "adversative", "determinant", etc. de marqueurs  et ses règles associées par exemple MAIS_RESTRICTIF # .items() retourne des paires (clé, valeur) : g = nom du groupe, rules = liste des règles associées
        for r in rules: #  ses règles associées par exemple MAIS_RESTRICTIF
            cues.extend(apply_marker_rule(r, text, seen_intervals)) # Applique la règle `r` au texte et ajoute toutes les cues détectées à la liste `cues`
    groups_present = sorted({c["group"] for c in cues})
    obj = {
        "id": sid,
        "text": text,
        "pipeline_step": "STEP1_DETERMINISTIC",
        # "candidates_rules_ID_cues": build_candidates_rules_id_cues(groups_present, markers_by_group),
        "cues": cues
    }
    return obj


def annotate_batch(lines: List[str], markers_by_group, strategies_by_id, order_by_group) -> List[Dict[str,Any]]:
    out = []
    sid = 0
    for line in lines:
        sid += 1
        text = line.strip()
        if not text:
            continue
        out.append(annotate_sentence(text, sid, markers_by_group, strategies_by_id, order_by_group))
    return out

__all__ = ["tokenize_with_offsets","load_markers","load_registry_and_scopes","annotate_sentence","annotate_batch","make_logger"]
