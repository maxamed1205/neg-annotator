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
- Ajout d'un coupeur lexical (stop_lexemes) pour couper la portée bipartite avant les concessives (ex. « malgré », « mais »).
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

DEFAULT_STOP_PUNCT = [",",";",":",".","!","?",")","]","}" ]
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
    return re.sub(r"\s+", " ", s.strip()).replace("’","'")

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
                flags = reg.IGNORECASE if rule.get("options",{}).get("case_insensitive") else 0
                rule["_compiled"] = reg.compile(pat, flags)
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
    out: List[Dict[str,Any]] = []
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
            pat = reg.compile(rule["when_pattern"], flags)
        except Exception:
            return out
    for m in pat.finditer(text):
        if _guard_hits(rule, text, m):
            continue
        label = _format_cue_label(rule.get("cue_label"), m)
        out.append({
            "id": rule.get("id","UNK_RULE"),
            "cue_label": normalize_spaces(label),
            "start": m.start(),
            "end": m.end(),
            "group": rule.get("group","unknown"),
        })
    return out


def _mk_cue(rule: Dict[str,Any], a:int,b:int, span:str) -> Dict[str,Any]:
    return {"id": rule.get("id","UNK_RULE"), "cue_label": span, "start": a, "end": b, "group": rule.get("group","unknown")}


def _guard_hits(rule: Dict[str,Any], text: str, match=None) -> bool:
    guards = rule.get("_guards") or []
    if not guards: return False
    window = text
    if match:
        a = max(0, match.start()-40); b = min(len(text), match.end()+40)
        window = text[a:b]
    return any(g.search(window) for g in guards)


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
    # Compléter certains marqueurs surface (ex. « malgré ») s'ils manquent
    cues = inject_surface_markers(text, cues)

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
