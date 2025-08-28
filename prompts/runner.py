#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Runner permissif v3 — 100% sans spaCy (full‑regex + tokenisation maison)

Ce build aligne la sortie sur le pipeline que tu demandes :
- Étape 1 (déterministe) : cues + scopes via règles YAML et stratégies surface.
- Étape 2 (LLM actions) : dicté par un contrat OBLIGATOIRE.
- Étape 3 (LLM ajouts) : champ "LLM_ajouts" réservé pour les compléments (sujet, supports, cues manquants),
  à remplir côté orchestrateur.

Diffs clés vs version précédente :
- Ajout d'un coupeur lexical (stop_lexemes) pour couper la portée bipartite avant les concessives (ex. « malgré    for i, (tok, a,     for i, (tok, a, b) in    for i, (tok,         is_part1 = t == "ne" or t.startswith("n'") or t.startswith("n'")
        if is_part1:
            # Déterminer le token de contraction et ses positions
            if t == "ne":
                contraction_token = "ne"
                contraction_start = a
            else:
                # Pour les contractions comme "n'ont", garder seulement "n'"
                contraction_token = t[:2]  # "n'" or "n'"
                contraction_start = a
            
            # search ahead within max_tokens tokens (excluding punctuation tokens)b) in enumerate(tokens):
        t = tok.lower()
        # un marqueur de début peut être "ne", ou bien un token débutant par "n'" ou "n'"
        # Gérer aussi les contractions séparées par le tokeniseur: "n" + "'"
        is_part1 = t == "ne" or t.startswith("n'") or t.startswith("n'")
        
        # Gérer le cas où "n'" est tokenisé en "n" + "'"
        contraction_start = a
        contraction_token = tok
        if t == "n" and i + 1 < len(tokens) and tokens[i + 1][0] in ["'", "'"]:
            is_part1 = True
            contraction_token = "n'"  # Reconstruire la contraction
            contraction_start = a
            
        if is_part1:erate(tokens):
        t = tok.lower()
        # un marqueur de début peut être "ne", ou bien un token débutant par "n'" ou "n'"
        # Gérer aussi les contractions séparées par le tokeniseur: "n" + "'"
        is_part1 = t == "ne" or t.startswith("n'") or t.startswith("n'")
        
        # Gérer le cas où "n'" est tokenisé en "n" + "'"
        contraction_end = b
        if t == "n" and i + 1 < len(tokens) and tokens[i + 1][0] in ["'", "'"]:
            is_part1 = True
            contraction_end = tokens[i + 1][2]  # End of apostrophe
            
        if is_part1: enumerate(tokens):
        t = tok.lower()
        print(f"[DEBUG] Checking token {i}: '{tok}' ('{t}')")
        # un marqueur de début peut être "ne", ou bien un token débutant par "n'" ou "n'"
        # Gérer aussi les contractions séparées par le tokeniseur: "n" + "'"
        is_part1 = t == "ne" or t.startswith("n'") or t.startswith("n'")
        
        # Gérer le cas où "n'" est tokenisé en "n" + "'"
        contraction_end = b
        if t == "n" and i + 1 < len(tokens) and tokens[i + 1][0] in ["'", "'"]:
            is_part1 = True
            contraction_end = tokens[i + 1][2]  # End of apostrophe
            print(f"[DEBUG] Found contraction: n + {tokens[i + 1][0]}")
            
        print(f"[DEBUG] is_part1: {is_part1}")
        if is_part1: mais »).
- Pré-détection déterministe de certaines prépositions concessives fréquentes (ex. « malgré ») si absentes des 10_markers.
- Stratégie préposition générique : PREP_GENERIC_CORE (utilisée pour PREP_SANS_CORE, PREP_MALGRÉ_CORE, etc.).
- Contrat LLM renforcé : MUST_COMPLETE_MISSING + rules_obligations (require_subject / require_support / require_cue_completion).
- Sortie enrichie : pipeline_step et placeholder LLM_ajouts.

Dépendances :
    pip install pyyaml regex

Entrées :
  --rules   : dossier racine contenant 10_markers/ et 20_scopes/
  --input   : fichier texte (1 phrase par ligne)
  --output  : JSONL intermédiaire
  --mode    : strict | permissive  (permissive = MUST_COMPLETE_MISSING)
"""

from __future__ import annotations
import argparse
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

import yaml
import regex as reg

# ----------------- logging -----------------

def make_logger(level="INFO"):
    logging.basicConfig(format='[%(levelname)s] %(message)s', level=getattr(logging, level.upper(), logging.INFO))
    return logging.getLogger("runner_v3")

log = make_logger()

# ----------------- tokenisation utils -----------------
PUNCT_RE = r"[,;:!?\.()\[\]{}«»“”\"']"
STOPWORDS = {"de","du","des","d'","d’","la","le","les","un","une","et","ou","à","au","aux","en","dans","sur","pour","par","avec","sans","que","ne","n’","n'","pas","plus","jamais","rien","personne","guère","point","aucun","aucune"}

DEFAULT_STOP_PUNCT = [",",";",":",".","!","?",""]   # Correction ici
# Lexèmes qui coupent naturellement une portée (concessives/mais)
DEFAULT_STOP_LEXEMES = ["malgré","mais","cependant","pourtant","toutefois","néanmoins"]


def tokenize_with_offsets(text: str) -> List[Tuple[str,int,int]]:
    toks: List[Tuple[str,int,int]] = []
    for m in re.finditer(r"\S+", text, flags=re.UNICODE):
        chunk = m.group(0)
        s = m.start()
        last = 0
        for pm in re.finditer(PUNCT_RE, chunk):
            if pm.start() > last:
                toks.append((chunk[last:pm.start()], s+last, s+pm.start()))
            toks.append((pm.group(0), s+pm.start(), s+pm.end()))
            last = pm.end()
        if last < len(chunk):
            toks.append((chunk[last:], s+last, s+len(chunk)))
    return [(t,a,b) for (t,a,b) in toks if t]


def window_right(tokens: List[Tuple[str,int,int]], start_char: int, max_tokens: int,
                 stop_punct: Optional[List[str]] = None,
                 stop_lexemes: Optional[List[str]] = None) -> Tuple[int,int]:
    """Collecte une fenêtre à droite jusqu'à ponctuation ou lexème coupeur."""
    stop = set(stop_punct or DEFAULT_STOP_PUNCT)
    cutters = {w.lower() for w in (stop_lexemes or DEFAULT_STOP_LEXEMES)}
    collected = []
    for tok,a,b in tokens:
        if a < start_char:
            continue
        if tok in stop:
            break
        if tok.lower() in cutters:
            break
        collected.append((a,b))
        if len(collected) >= max_tokens:
            break
    if not collected:
        return -1,-1
    return collected[0][0], collected[-1][1]


def strip_leading_de(span: str) -> str:
    return re.sub(r"^(?:de|d’|d')\s+", "", span, flags=re.IGNORECASE)


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()).replace("’", "'").replace("\u2019", "'")

# ----------------- chargement YAML -----------------

def _iter_yaml_files(folder: Path) -> List[Path]:
    return sorted([p for p in folder.glob("*.yaml") if p.is_file() and not p.name.startswith("_")])


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


def load_markers(rules_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    d = rules_dir / "10_markers"
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for f in _iter_yaml_files(d):
        items = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not isinstance(items, list):
            continue
        for rule in items:
            rule["_file"] = str(f)
            gid = rule.get("group") or infer_group_from_filename(f.name)
            rule["group"] = gid
            pat = rule.get("when_pattern")
            if pat:
                # Nettoyer le pattern YAML avant compilation - méthode plus robuste
                # 1. Supprimer tous les retours à la ligne
                clean_pattern = pat.replace('\n', '')
                # 2. Normaliser les espaces multiples mais préserver les \s dans regex
                clean_pattern = re.sub(r'(?<!\\)\s+', '', clean_pattern)
                # 3. Remettre des espaces autour des | si nécessaire
                clean_pattern = re.sub(r'\|', '|', clean_pattern)
                
                flags = reg.IGNORECASE if rule.get("options",{}).get("case_insensitive") else 0
                rule["_compiled"] = reg.compile(clean_pattern, flags)
                rule["_clean_pattern"] = clean_pattern  # Garder le pattern nettoyé pour debug
            comp_guards = []
            for g in rule.get("negative_guards", []) or []:
                gp = g.get("pattern") if isinstance(g, dict) else g
                if gp:
                    comp_guards.append(reg.compile(gp, reg.IGNORECASE))
            if comp_guards:
                rule["_guards"] = comp_guards
            grouped.setdefault(gid, []).append(rule)
    for g,L in grouped.items():
        log.info("Markers '%s': %d règles", g, len(L))
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

# ----------------- détection des cues (10_markers) -----------------

def apply_marker_rule(rule: Dict[str,Any], text: str) -> List[Dict[str,Any]]:
    """Apply a single marker rule to the input text and return a list of cue objects.

    The rules defined in ``10_markers`` can be of different natures: some are pure
    detection patterns (which should emit a cue when their ``when_pattern`` matches),
    and some are quality‑control or guard rules (which are described by the ``action``
    field or have an id starting with ``QC_``). QC rules do not correspond to
    negation markers themselves; instead they instruct the LLM to perform a
    validation or repair on the cues produced by the deterministic layer. If we
    treat them like any other detection rule, they end up generating bogus cues
    that cover the entire sentence or empty spans. To avoid polluting the cue
    output, we simply skip any rule that declares an ``action`` or whose ``id``
    starts with ``QC_``. These rules are forwarded to the LLM via
    ``pending_rules`` but do not create cues here.
    """
    out: List[Dict[str,Any]] = []
    # -------------------------------------------------------------------------
    # Skip QC/validation rules: they shouldn't emit cues. We detect them via
    # the presence of an "action" field or an id starting with "QC_".
    if rule.get("action") or (str(rule.get("id", "")).upper().startswith("QC_")):
        logging.debug(f"Skipping QC rule: {rule.get('id')}")
        return out

    # Log the rule being applied
    logging.debug(f"Applying rule: {rule.get('id')} to text: {text}")

    pat = rule.get("_compiled")
    if not pat and not rule.get("when_pattern"):
        wm = rule.get("when_marker")
        if wm:
            for m in re.finditer(rf"\b{re.escape(wm)}\b", text, flags=re.IGNORECASE):
                if not _guard_hits(rule, text, m):
                    out.append(_mk_cue(rule, m.start(), m.end(), text[m.start():m.end()]))
        return out
    if not pat:
        flags = reg.IGNORECASE if rule.get("options",{}).get("case_insensitive") else 0
        try:
            # Si pas de pattern précompilé, compiler maintenant avec nettoyage
            raw_pattern = rule["when_pattern"]
            clean_pattern = re.sub(r'\n\s*\|', '|', raw_pattern)
            clean_pattern = re.sub(r'\n\s+', '', clean_pattern)
            
            pat = reg.compile(clean_pattern, flags)
            logging.debug(f"Compiled pattern for rule {rule.get('id')}: {clean_pattern} with flags: {flags}")
        except Exception as e:
            logging.error(f"Failed to compile pattern for rule {rule.get('id')}: {rule.get('when_pattern')} - Error: {e}")
            return out
    
    logging.debug(f"Searching for pattern in text: '{text}' with compiled pattern: {pat.pattern}")
    matches_found = 0
    for m in pat.finditer(text):
        matches_found += 1
        logging.debug(f"Found match for rule {rule.get('id')}: {m.group()} at position {m.start()}-{m.end()}")
        if _guard_hits(rule, text, m):
            logging.debug(f"Match blocked by guards for rule {rule.get('id')}")
            continue
        
        # Handle exclude_verbs_from_cue option
        start_pos = m.start()
        end_pos = m.end()
        span_text = text[start_pos:end_pos]
        
        # TOUJOURS exclure les verbes pour les marqueurs bipartites (requis par l'utilisateur)
        exclude_verbs = rule.get("options", {}).get("exclude_verbs_from_cue", False)
        
        # Force l'exclusion des verbes pour TOUS les groupes bipartites
        if rule.get("group") == "bipartite":
            exclude_verbs = True
        
        if exclude_verbs:
            # Extract only negation markers, excluding verbs
            span_text, start_pos, end_pos = _extract_negation_markers_only(text, m, rule)
            logging.debug(f"Excluded verbs from cue for rule {rule.get('id')}: '{span_text}' at {start_pos}-{end_pos}")
        
        label = _format_cue_label(rule.get("cue_label"), m)
        if exclude_verbs and not label:
            label = span_text
            
        cue = {
            "id": rule.get("id","UNK_RULE"),
            "cue_label": normalize_spaces(label if label else span_text),
            "start": start_pos,
            "end": end_pos,
            "group": rule.get("group","unknown"),
        }
        logging.debug(f"Created cue from rule {rule.get('id')}: {cue}")
        out.append(cue)
    
    if matches_found == 0:
        logging.debug(f"No matches found for rule {rule.get('id')} in text: '{text}'")
    else:
        logging.debug(f"Rule {rule.get('id')} produced {len(out)} cues from {matches_found} matches")
    
    return out


def _extract_negation_markers_only(text: str, match, rule: Dict[str, Any]) -> Tuple[str, int, int]:
    """
    Extract only negation markers from a match, excluding verbs.
    
    This function handles the exclude_verbs_from_cue option by:
    1. Identifying negation particles (ne, n', pas, jamais, plus, etc.)
    2. Excluding verbs that appear between or around these particles
    3. Returning the cleaned span containing only negation markers
    """
    import re
    
    match_text = match.group(0).strip()
    match_start = match.start()
    match_end = match.end()
    
    # Detect bipartite patterns: "ne/n' ... pas/plus/jamais/rien/personne/etc"
    # This regex finds the first negation particle and the second one, excluding verbs in between
    bipartite_pattern = r"\b(n['']?|ne)\b.*?\b(pas|plus|jamais|rien|personne|guère|point|nul)\b"
    bipartite_match = re.search(bipartite_pattern, match_text, re.IGNORECASE)
    
    if bipartite_match:
        # Extract the two particles separately
        part1_pattern = r"\b(n['']?|ne)\b"
        part2_pattern = r"\b(pas|plus|jamais|rien|personne|guère|point|nul)\b"
        
        part1_match = re.search(part1_pattern, match_text, re.IGNORECASE)
        part2_match = re.search(part2_pattern, match_text, re.IGNORECASE)
        
        if part1_match and part2_match:
            part1_text = part1_match.group(1)
            part2_text = part2_match.group(1)
            
            # Create label with only negation particles (no verbs)
            cleaned_label = f"{part1_text} {part2_text}"
            
            # Return positions of the full match but cleaned label
            return cleaned_label, match_start, match_end
    
    # Single negation particles (non-bipartite)
    single_neg_patterns = [
        r"\b(ne|n[''])\b",       # ne, n'
        r"\b(pas)\b",            # pas
        r"\b(plus)\b",           # plus
        r"\b(jamais)\b",         # jamais
        r"\b(rien)\b",           # rien
        r"\b(personne)\b",       # personne
        r"\b(guère)\b",          # guère
        r"\b(point)\b",          # point
        r"\b(nul)\b",            # nul
        r"\b(aucun|aucune)\b",   # aucun, aucune
        r"\b(sans)\b",           # sans
        r"\b(ni)\b",             # ni
        r"\b(non)\b",            # non
        r"\b(absence)\b",        # absence
    ]
    
    for pattern in single_neg_patterns:
        single_match = re.search(pattern, match_text, re.IGNORECASE)
        if single_match:
            particle_text = single_match.group(1)
            # For single particles, use their exact position within the match
            particle_start = match_start + single_match.start(1)
            particle_end = match_start + single_match.end(1)
            return particle_text, particle_start, particle_end
    
    # Fallback: if no recognizable negation particles found, return original
    return match_text, match_start, match_end


def _mk_cue(rule: Dict[str,Any], a:int,b:int, span:str) -> Dict[str,Any]:
    cue = {"id": rule.get("id","UNK_RULE"), "cue_label": span, "start": a, "end": b, "group": rule.get("group","unknown")}
    logging.debug(f"Created cue: {cue}")
    return cue


def _guard_hits(rule: Dict[str,Any], text: str, match=None) -> bool:
    guards = rule.get("_guards") or []
    if not guards:
        logging.debug(f"No guards defined for rule: {rule.get('id')}")
        return False

    window = text
    if match:
        a = max(0, match.start()-40); b = min(len(text), match.end()+40)
        window = text[a:b]

    result = any(g.search(window) for g in guards)
    logging.debug(f"Guard check for rule: {rule.get('id')} in window: '{window}' - Result: {result}")
    return result


def _format_cue_label(lbl, m) -> str:
    if lbl is None:
        return m.group(0)
    if isinstance(lbl, list):
        for cand in lbl:
            try:
                v = cand.format(**m.groupdict(default="")).strip()
            except Exception:
                v = cand
            if v:
                return v
        return lbl[0]
    if isinstance(lbl, str):
        try:
            return lbl.format(**m.groupdict(default="")).strip()
        except Exception:
            return lbl
    return str(lbl)

# ----------------- compléments déterministes (prépositions concessives) -----------------
# Certains corpus n'ont pas de règle 10_markers pour « malgré ». On l'ajoute de façon déterministe si absent.
SURFACE_PREP_MARKERS = {
    "malgré": {"id": "PREP_MALGRÉ", "group": "preposition", "cue_label": "malgré"},
}

def inject_surface_markers(text: str, cues: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    tlow = text.lower()
    have = {(c["group"], c["cue_label"].lower()) for c in cues}
    added: List[Dict[str,Any]] = []
    for lex, meta in SURFACE_PREP_MARKERS.items():
        if (meta["group"], lex) in have:
            continue
        for m in re.finditer(rf"\b{re.escape(lex)}\b", tlow):
            a,b = m.start(), m.end()
            added.append({
                "id": meta["id"],
                "group": meta["group"],
                "cue_label": meta["cue_label"],
                "start": a,
                "end": b,
            })
    return cues + added

# ----------------- guards de stratégie (20_scopes) -----------------

def guard_deny_if_surface(strategy: Dict[str,Any], text: str) -> bool:
    cfg = (strategy.get("guards") or {}).get("deny_if_surface")
    if not cfg: return False
    for g in cfg:
        pat = g.get("pattern") if isinstance(g, dict) else g
        if not pat: continue
        flags = reg.IGNORECASE if (isinstance(g, dict) and ((g.get("options") or {}).get("case_insensitive"))) else 0
        rx = reg.compile(pat, flags)
        if rx.search(text):
            return True
    return False

# ----------------- exécution des stratégies (sans spaCy) -----------------

def exec_strategy(group: str, sid: str, strat: Dict[str,Any], text: str, tokens,
                  cues_for_group: List[Dict[str,Any]], all_group_scopes: Dict[str,List[Dict[str,Any]]]) -> List[Dict[str,Any]]:
    stype = strat.get("scope_strategy") or ""
    opts = strat.get("options") or {}

    # deny_if_surface
    if guard_deny_if_surface(strat, text):
        return []

    # === SKIP_IF_PATTERN ===
    if stype == "SKIP_IF_PATTERN":
        pat = (opts or {}).get("pattern")
        if pat and reg.search(pat, text):
            return [{"_skip_group": group, "strategy": sid}]
        return []

    # === SKIP_IF_LEXICALIZED (prépositions lexicalisées) ===
    if stype == "SKIP_IF_LEXICALIZED":
        patterns = (opts or {}).get("lexicalized_patterns", [])
        for p in patterns:
            if re.search(rf"\b{re.escape(p)}\b", text, flags=re.IGNORECASE):
                return [{"_skip_group": group, "strategy": sid}]
        return []

    # === NEP_SMART (bipartite core) ===
    if stype == "NEP_SMART" or (sid.endswith("_CORE") and group=="bipartite"):
        out = []
        for c in cues_for_group:
            out.append({
                "id": sid if sid else "BIP_G_CORE",
                "scope": "<LLM_APPLY_RULE>",   # placeholder, scope final attendu du LLM
                "start": c["end"],
                "end": -1,
                "llm_instruction": {
                    "policy": "READ_AND_APPLY_RULE",
                    "rule_id": sid,
                    "rule_yaml": strat,   # dump complet de la règle YAML
                    "cue": c,
                    "text": text,
                    "notes": "Relis la règle YAML, écris la règle, applique-la au cue pour générer le scope correct. Respecte start/end."
                }
            })
        return out


    # === DET_NEG_GN_SMART (determinant core) ===
    if stype == "DET_NEG_GN_SMART" or (sid.endswith("_CORE") and group=="determinant"):
        out=[]
        max_tokens = int(opts.get("max_token_gap", 8))
        stop_punct = opts.get("stop_punct") or DEFAULT_STOP_PUNCT
        stop_lexemes = opts.get("stop_lexemes") or DEFAULT_STOP_LEXEMES
        strip_de = opts.get("strip_de", True)
        for c in cues_for_group:
            a,b = window_right(tokens, c["end"], max_tokens, stop_punct, stop_lexemes)
            if a==-1: continue
            span = normalize_spaces(text[a:b])
            if strip_de: span = strip_leading_de(span)
            sa = text.lower().find(span.lower(), c["end"]) ; sb = sa + len(span) if sa!=-1 else -1
            out.append({"id": sid if sid else "DET_G_CORE", "scope": span, "start": sa, "end": sb})
        return dedup(out)

    # === PREP cores (générique) ===
    if stype in {"PREP_SANS_CORE","PREP_MALGRÉ_CORE","PREP_GENERIC_CORE"} or (sid.endswith("_CORE") and group=="preposition"):
        out=[]
        max_tokens = int(opts.get("right_window_tokens", 10))
        stop_punct = opts.get("stop_punct") or DEFAULT_STOP_PUNCT
        stop_lexemes = opts.get("stop_lexemes") or DEFAULT_STOP_LEXEMES
        for c in cues_for_group:
            a,b = window_right(tokens, c["end"], max_tokens, stop_punct, stop_lexemes)
            if a==-1: continue
            span = strip_leading_de(normalize_spaces(text[a:b]))
            out.append({"id": sid or "PREP_GENERIC_CORE", "scope": span, "start": a, "end": b})
        return dedup(out)

    # === NI coord ===
    if stype in {"NI_COORD_SMART","NI_SIMPLE_SPLIT"} or (sid.endswith("_CORE") and group=="conjonction"):
        out=[]
        tlow = text.lower()
        parts = re.split(r"\bni\b", tlow)
        for part in parts[1:]:
            frag = part.strip()
            if not frag: continue
            frag = re.split(PUNCT_RE, frag)[0].strip()
            if not frag: continue
            a = tlow.find(frag)
            if a!=-1:
                b = a+len(frag)
                out.append({"id": sid if sid else "CONJ_NI_CORE", "scope": text[a:b], "start": a, "end": b})
        return dedup(out)

    # === COOC_DET_RESOLVE (bipartite <-> determinant) ===
    if stype == "RESOLVE_COOCURRENCE" or sid.endswith("COOC_DET_RESOLVE"):
        out=[]
        bip = all_group_scopes.get("bipartite", [])
        det = all_group_scopes.get("determinant", [])
        for b1 in bip:
            for d1 in det:
                if spans_overlap(b1, d1) >= 0.5:
                    a = min(b1["start"], d1["start"]) ; c = max(b1["end"], d1["end"])
                    out.append({"id": sid, "scope": normalize_spaces(text[a:c]), "start": a, "end": c})
        return dedup(out)

    # === GOVERNOR_SUPPORT_AUTO (supports surface) ===
    if stype == "GOVERNOR_SUPPORT_AUTO":
        out=[]
        for pre in ["selon","d'après","d’\u2009après","conformément à","au regard de","en accord avec","par"]:
            m_iter = re.finditer(rf"\b{re.escape(pre)}\b\s+([^.,;:]+)", text, flags=re.IGNORECASE)
            for m in m_iter:
                a = m.start(1); b = m.end(1)
                out.append({"id": sid, "role": "support", "scope": normalize_spaces(text[a:b]), "start": a, "end": b})
        # Titre à gauche avant ':'
        m = re.search(r"(^|[\n\.])([^\n:\.]{3,})\s*:[\s\-–—]*$", text)
        if m:
            a = m.start(2); b = m.end(2)
            out.append({"id": sid, "role": "support", "scope": normalize_spaces(text[a:b]), "start": a, "end": b})
        return dedup(out)

    # Fallback: when_pattern au niveau stratégie
    wpat = strat.get("when_pattern")
    if wpat:
        flags = reg.IGNORECASE if (strat.get("options") or {}).get("case_insensitive") else 0
        rx = reg.compile(wpat, flags)
        out=[]
        for m in rx.finditer(text):
            a,b = m.start(), m.end()
            out.append({"id": sid, "scope": normalize_spaces(text[a:b]), "start": a, "end": b})
        return dedup(out)

    return []

# ----------------- chevauchements & QC -----------------

def spans_overlap(x, y) -> float:
    a1,a2 = x["start"], x["end"]; b1,b2 = y["start"], y["end"]
    inter = max(0, min(a2,b2) - max(a1,b1))
    den = max(a2,b2) - min(a1,b1)
    return inter/den if den>0 else 0.0


def qc_trim_appositions(text: str, span: Dict[str,Any]) -> Dict[str,Any]:
    tail = text[span["start"]:span["end"]]
    for t in [", selon", ", d'après", ", d’\u2009après", ", conformément à", ", au regard de", ", en accord avec"]:
        idx = tail.lower().find(t)
        if idx != -1:
            span["end"] = span["start"] + idx
            span["scope"] = normalize_spaces(text[span["start"]:span["end"]])
            break
    return span


def apply_qc(scopes: List[Dict[str,Any]], text: str) -> List[Dict[str,Any]]:
    out=[]
    for s in scopes:
        if s.get("role") == "support":
            out.append(s); continue
        if s.get("start",-1)>=0 and s.get("end",-1)>=0:
            s = qc_trim_appositions(text, s)
        out.append(s)
    return dedup(out)


def dedup(spans: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    seen=set(); out=[]
    for s in spans:
        key=(s.get("id"), s.get("start"), s.get("end"), s.get("role"))
        if key in seen: continue
        seen.add(key); out.append(s)
    return out

# -----------------------------------------------------------------------------
# Détection bipartite cross‑tokens
# -----------------------------------------------------------------------------

def detect_bipartite_cross_tokens(text: str, tokens: List[Tuple[str,int,int]], existing_cues: List[Dict[str,Any]], rule: Dict[str,Any]) -> List[Dict[str,Any]]:
    """
    Détecte les marqueurs bipartites de type « ne … pas » lorsque les deux
    éléments sont séparés par un ou plusieurs tokens. La logique est guidée par
    les options ``max_token_gap`` définies dans la règle YAML. Les listes des
    particules de départ (part1) et de fin (part2) sont dérivées du YAML
    (voir ``bipartites.yaml``) pour NE_BIPARTITE_EXTENDED.

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
    part1_set = {"ne", "n'", "n’"}
    part2_set = {"pas", "plus", "jamais", "rien", "personne", "guère", "point", "nul"}
    existing_keys = {(c.get("id"), c.get("start"), c.get("end")) for c in existing_cues}
    for i, (tok, a, b) in enumerate(tokens):
        t = tok.lower()
        # un marqueur de début peut être "ne", ou bien un token débutant par "n'" ou "n’"
        is_part1 = t == "ne" or t.startswith("n'") or t.startswith("n’")
        if is_part1:
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
                    key = (rule.get("id"), a, b2)
                    if key not in existing_keys:
                        # TOUJOURS exclure les verbes pour les bipartites (requis par l'utilisateur)
                        # Créer un label avec seulement les particules de négation
                        label = normalize_spaces(t[:2] + " " + t2) if t.startswith("n'") or t.startswith("n'") else normalize_spaces("ne " + t2)
                        # Pour les positions, utiliser le span complet mais le label ne contient que les particules
                        cue_start = a  # Start of "ne/n'"
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

# ----------------- contrat LLM -----------------
NEG_LEXEMES_HINTS = {
    "bipartite": ["ne","n’","n'","pas","plus","jamais","rien","personne","guère","point","nul"],
    "determinant": ["aucun","aucune","aucuns","aucunes","pas de","pas d’","pas d'"],
    "preposition": ["sans","hors de","en dehors de","malgré"],
    "conjonction": ["ni"],
    "lexical": ["non","inefficace","impossible","absent","absence","nul","nulle"],
    "locution": ["à l’exception de","à l'exclusion de","privation de","faute de"],
    "adversative": ["mais"],
}


def make_llm_contract(mode: str, text: str, cues: List[Dict[str,Any]]) -> Dict[str,Any]:
    if mode=="strict":
        return {"mode":"strict"}
    found_texts = {c["cue_label"].lower() for c in cues}
    tlow = text.lower()
    hints=[]
    missing_groups=[]
    for g, lex in NEG_LEXEMES_HINTS.items():
        present=False
        for w in lex:
            if w.lower() in tlow:
                present=True
                if w.lower() not in found_texts:
                    hints.append({"group": g, "lexeme": w})
        if present and g not in {c["group"] for c in cues}:
            missing_groups.append(g)
    policy=(
        "MUST_COMPLETE_MISSING: Tu DOIS compléter tout sujet, support ET tout marqueur manquant "
        "en respectant les règles YAML. "
        "Exécute aussi toutes les pending_rules fournies : relis la règle, écris la règle et applique-la au cue."
        
        "MUST_COMPLETE_MISSING: Tu DOIS compléter tout sujet, support ET tout marqueur manquant en respectant les règles YAML. "
        "Priorité absolue aux candidats du runner. Si un lexème/structure indique une négation non couverte, "
        "ajoute-la avec id='LLM_FALLBACK' et group='inference', puis calcule la portée avec les mêmes stratégies. "
        "Fusionne les scopes identiques. Respecte strictement le schéma de sortie."
    )
    rules_obligations = [
        {"id":"BIP_G_CORE","require_subject": True, "description":"Inclure le sujet grammatical dans une portée distincte."},
        {"id":"GOVERNOR_SUPPORT_AUTO","require_support": True, "description":"Inclure les entités de support normatives (selon, d’après, etc.)."},
        {"id":"ALL_MARKERS","require_cue_completion": True, "description":"Compléter les marqueurs manquants si un lexème connu apparaît, même si redondant."},
    ]
    fallback_schema={
        "cue": {"id":"LLM_FALLBACK","group":"inference","cue_label":"<forme canonique>","start":-1,"end":-1},
        "scope": {"id":"<STRATEGY_ID>","scope":"<texte>","start":-1,"end":-1}
    }
    return {
        "mode":"permissive_mandatory_completion",
        "policy":policy,
        "rules_obligations": rules_obligations,
        "hints":{"lexeme_hits":hints,"missing_groups":missing_groups},
        "fallback_schema":fallback_schema
    }

# ----------------- builders -----------------

def build_candidates_rules_id_cues(groups_present: List[str], markers_by_group: Dict[str,List[Dict[str,Any]]]) -> List[Dict[str,Any]]:
    out=[]
    for g in groups_present:
        out.append({"group": g, "rules": [r.get("id","UNK_RULE") for r in markers_by_group.get(g,[])]})
    return out


def build_candidates_rules_id_scopes(groups_present: List[str], order_by_group: Dict[str,List[str]]) -> List[Dict[str,Any]]:
    out=[]
    for g in groups_present:
        out.append({"group": g, "rules": list(order_by_group.get(g, []))})
    return out

# ----------------- annotation d'une phrase -----------------

def annotate_sentence(text: str, sid: int, markers_by_group, strategies_by_id, order_by_group, mode: str) -> Dict[str,Any]:
    tokens = tokenize_with_offsets(text)

    # 1) cues déterministes (10_markers)
    cues: List[Dict[str,Any]] = []
    for g, rules in markers_by_group.items():
        for r in rules:
            cues.extend(apply_marker_rule(r, text))

    # Détection additionnelle pour les marqueurs bipartites avec un écart de tokens (ne … pas, ne … plus, etc.).
    # Certaines expressions comme « n'ont pas » ou « ne … jamais » contiennent un ou plusieurs
    # tokens intermédiaires entre les deux parties du marqueur. Les motifs regex présents
    # dans les YAML ne capturent que les cas contigus (« ne pas ») et ne tiennent pas compte
    # des options « max_token_gap » définies dans les règles. Ici, nous reconstruisons ces
    # marqueurs à partir des tokens lorsque la règle NE_BIPARTITE_EXTENDED est définie.
    if "bipartite" in markers_by_group:
        for r in markers_by_group["bipartite"]:
            if r.get("id") == "NE_BIPARTITE_EXTENDED":
                cues.extend(detect_bipartite_cross_tokens(text, tokens, cues, r))
                break
    # Compléter certains marqueurs surface (ex. « malgré ») s'ils manquent
    cues = inject_surface_markers(text, cues)
    # Déduplication des cues : plusieurs règles peuvent détecter le même marqueur
    # (ex. la préposition « sans » capturée par preposition.yaml et locutions.yaml).
    # Afin de respecter le format « un cue = un seul id et un seul group », nous
    # éliminons les doublons exacts sur (id, group, cue_label, start, end). Cela
    # conserve un seul objet par occurrence et évite les répétitions dans la sortie.
    unique_cues: Dict[tuple, Dict[str,Any]] = {}
    for c in cues:
        key = (c.get("id"), c.get("group"), c.get("cue_label"), c.get("start"), c.get("end"))
        if key not in unique_cues:
            unique_cues[key] = c
    cues = list(unique_cues.values())

    groups_present = sorted({c["group"] for c in cues})

    # 2) scopes par groupe (ordre registry)
    group_scopes: Dict[str,List[Dict[str,Any]]] = {g: [] for g in groups_present}
    for g in groups_present:
        strats = order_by_group.get(g, [])
        for sid_ in strats:
            strat = strategies_by_id.get(sid_)
            if not strat: continue
            if strat.get("when_group") and strat.get("when_group") != g:
                continue
            res = exec_strategy(g, sid_, strat, text, tokens, [c for c in cues if c["group"]==g], group_scopes)
            if res and any("_skip_group" in r for r in res):
                group_scopes[g] = []
                break
            group_scopes[g].extend(res)

    # 3) QC
    all_scopes = [s for L in group_scopes.values() for s in L]
    all_scopes = apply_qc(all_scopes, text)

    # ➕ Nouveau : collecter les instructions LLM
    pending = []
    for s in all_scopes:
        if "llm_instruction" in s:
            pending.append(s["llm_instruction"])
            del s["llm_instruction"]   # on ne garde pas dans scopes

    # 4) objet final (Étape 1)
    obj = {
        "id": sid,
        "text": text,
        "pipeline_step": "STEP1_DETERMINISTIC",
        "candidates_rules_ID_cues": build_candidates_rules_id_cues(groups_present, markers_by_group),
        "cues": cues,
        "candidates_rules_ID_scopes": build_candidates_rules_id_scopes(groups_present, order_by_group),
        "scopes": [
            {"id": s.get("id","CORE"), "scope": s.get("scope",""),
             "start": s.get("start",-1), "end": s.get("end",-1),
             **({"role": s["role"]} if "role" in s else {})}
            for s in all_scopes
        ],
        # 🔥 Ici on fusionne avec make_llm_contract
        "llm_contract": {
            **make_llm_contract(mode, text, cues),
            "pending_rules": pending
        },
        "LLM_actions": [],
        "LLM_ajouts": {"cues": [], "scopes": []}
    }
    return obj

# ----------------- CLI -----------------

def main():
    ap = argparse.ArgumentParser(description="Runner permissif v3 (no-NLP, pipeline renforcé)")
    ap.add_argument("--rules", required=True, help="Chemin dossier rules/")
    ap.add_argument("--input", required=True, help="Fichier texte (1 phrase/ligne)")
    ap.add_argument("--output", required=True, help="Sortie JSONL")
    ap.add_argument("--mode", default="permissive", choices=["permissive","strict"], help="Mode LLM")
    ap.add_argument("--log", default="INFO")
    args = ap.parse_args()

    global log; log = make_logger(args.log)

    rules_dir = Path(args.rules)
    markers_by_group = load_markers(rules_dir)
    strategies_by_id, order_by_group = load_registry_and_scopes(rules_dir)

    sid=0
    with open(args.input, "r", encoding="utf-8") as fin, open(args.output, "w", encoding="utf-8") as fout:
        for line in fin:
            text = line.strip()
            if not text: continue
            sid += 1
            obj = annotate_sentence(text, sid, markers_by_group, strategies_by_id, order_by_group, args.mode)
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    log.info("Terminé: %d phrases → %s", sid, args.output)

if __name__ == "__main__":
    main()
