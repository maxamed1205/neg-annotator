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
                # 1. Remplacer les retours à la ligne par un espace (préserver la séparation des tokens)
                clean_pattern = pat.replace('\n', ' ')
                # 2. Réduire les espaces multiples en un seul espace (préserver les constructions regex comme \s+)
                clean_pattern = re.sub(r'\s+', ' ', clean_pattern).strip()
                # 3. Normaliser les espaces autour des alternations et des parenthèses pour éviter
                #    les tokens préfixés par des espaces causés par l'indentation YAML.
                clean_pattern = re.sub(r'\s*\|\s*', '|', clean_pattern)
                clean_pattern = re.sub(r'\(\s+', '(', clean_pattern)
                clean_pattern = re.sub(r'\s+\)', ')', clean_pattern)
                # 4. Enregistrer le pattern nettoyé
                # Remove spaces that may remain after named-group closing '>' (e.g. '(?P<name> ') -> '(?P<name>')
                clean_pattern = re.sub(r'>\s+', '>', clean_pattern)
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
    
    # Normalize typographic apostrophes for matching only (preserve original text for labels)
    text_for_match = text.replace("’", "'").replace("\u2019", "'")
    logging.debug(f"Searching for pattern in normalized text: '{text_for_match}' with compiled pattern: {pat.pattern}")
    matches_found = 0
    for m in pat.finditer(text_for_match):
        matches_found += 1
        matched = m.group()
        logging.debug(f"Found match for rule {rule.get('id')} (normalized): {matched} at position {m.start()}-{m.end()}")
        # Map match positions from normalized text back to original text
        # Strategy: locate the matched substring in the original text near the normalized index
        approx_start = m.start()
        # compute a search window in original text around approx_start
        window_start = max(0, approx_start - 40)
        window_end = min(len(text), approx_start + 40 + len(matched))
        window = text[window_start:window_end]
        # try to find matched substring in window (allowing different apostrophe forms)
        alt_matched = matched.replace("'", "['’]")
        try:
            finder = re.search(re.escape(matched).replace("\\'", "'") , window)
        except Exception:
            finder = None
        if finder:
            orig_start = window_start + finder.start()
            orig_end = window_start + finder.end()
        else:
            # fallback: map by length near approx_start
            orig_start = min(len(text), max(0, approx_start))
            orig_end = min(len(text), orig_start + len(matched))
        logging.debug(f"Mapped normalized match to original text positions: {orig_start}-{orig_end} -> '{text[orig_start:orig_end]}'")
        # Recreate a fake match object-like minimal interface for guard and extraction functions
        class _FakeMatch:
            def __init__(self, s, e, g, orig_match=None):
                # s,e : start/end in original text
                # g : matched text (original span)
                # orig_match : optional original regex match object from normalized text
                self._s = s
                self._e = e
                self._g = g
                self._orig = orig_match
            def start(self):
                return self._s
            def end(self):
                return self._e
            def group(self, *args):
                # behave like real match.group: if original match available delegate
                if self._orig is not None:
                    try:
                        return self._orig.group(*args)
                    except Exception:
                        pass
                if not args:
                    return self._g
                # support group(0) or group(1) by returning full match for 0 or g for any
                if args[0] == 0:
                    return self._g
                return self._g
            def groupdict(self, default=None):
                if self._orig is not None:
                    try:
                        return self._orig.groupdict(default=default)
                    except Exception:
                        return {}
                return {}
        fake_m = _FakeMatch(orig_start, orig_end, text[orig_start:orig_end])
        if _guard_hits(rule, text, fake_m):
            logging.debug(f"Match blocked by guards for rule {rule.get('id')}")
            continue
        
        # Handle exclude_verbs_from_cue option
        start_pos = fake_m.start()
        end_pos = fake_m.end()
        span_text = text[start_pos:end_pos]

        # TOUJOURS exclure les verbes pour les marqueurs bipartites (requis par l'utilisateur)
        exclude_verbs = rule.get("options", {}).get("exclude_verbs_from_cue", False)

        # Force l'exclusion des verbes pour TOUS les groupes bipartites
        if rule.get("group") == "bipartite":
            exclude_verbs = True

        if exclude_verbs:
            # Extract only negation markers, excluding verbs
            span_text, start_pos, end_pos = _extract_negation_markers_only(text, fake_m, rule)
            logging.debug(f"Excluded verbs from cue for rule {rule.get('id')}: '{span_text}' at {start_pos}-{end_pos}")

        label = _format_cue_label(rule.get("cue_label"), fake_m)
        if exclude_verbs:
            # Quand on exclut les verbes, utiliser TOUJOURS span_text et ignorer le label du YAML
            label = span_text
            logging.debug(f"Forcing cue label to span_text for verb exclusion: '{label}'")
            
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
    # Accept both ASCII and typographic apostrophes and ensure we capture only the particle (n' or ne)
    bipartite_pattern = r"(?:\bne\b|n['’]).*?\b(pas|plus|jamais|rien|personne|guère|point|nul)\b"
    bipartite_match = re.search(bipartite_pattern, match_text, re.IGNORECASE)
    
    if bipartite_match:
        # Extract the two particles separately, preserving their EXACT form from the text
        part1_pattern = r"(?:\bne\b|n['’])"
        part2_pattern = r"\b(pas|plus|jamais|rien|personne|guère|point|nul)\b"

        part1_match = re.search(part1_pattern, match_text, re.IGNORECASE)
        part2_match = re.search(part2_pattern, match_text, re.IGNORECASE)

        if part1_match and part2_match:
            # IMPORTANT: Préserver la forme EXACTE trouvée dans le texte (n' vs ne)
            # Trim trailing verb if part1 is like "n'" followed by a verb capture
            part1_text = part1_match.group(0)
            # If part1 ends with an apostrophe, ensure only the particle is kept
            if re.match(r"^n['’]", part1_text, re.IGNORECASE):
                part1_text = re.match(r"^n['’]", part1_text, re.IGNORECASE).group(0)
            part2_text = part2_match.group(0)  # group(0) pour garder la forme exacte

            # Create label with only negation particles (no verbs) but preserving exact forms
            cleaned_label = f"{part1_text} {part2_text}"
            
            # Compute precise positions for the particles within the original text
            p1_start = match_start + part1_match.start()
            p1_end = match_start + part1_match.end()
            p2_start = match_start + part2_match.start()
            p2_end = match_start + part2_match.end()
            # Return label and the span from start of part1 to end of part2
            return cleaned_label, p1_start, p2_end
    
    # Single negation particles (non-bipartite)
    single_neg_patterns = [
        r"(?:\bne\b|n['’])",       # ne, n' (handle typographic apostrophe)
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
            # IMPORTANT: Préserver la forme EXACTE trouvée dans le texte
            particle_text = single_match.group(0)  # group(0) pour garder la forme exacte
            # For single particles, use their exact position within the match
            particle_start = match_start + single_match.start()
            particle_end = match_start + single_match.end()
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
        # Fallback deterministic bipartite scope extraction (sans LLM):
        # On prend une fenêtre à droite (window_right) en respectant les tokens
        # et la ponctuation configurée dans la règle YAML.
        out = []
        max_tokens = int((strat.get("options") or {}).get("max_token_gap", 8))
        stop_punct = (strat.get("options") or {}).get("stop_punct") or DEFAULT_STOP_PUNCT
        stop_lexemes = (strat.get("options") or {}).get("stop_lexemes") or DEFAULT_STOP_LEXEMES
        for c in cues_for_group:
            a,b = window_right(tokens, c["end"], max_tokens, stop_punct, stop_lexemes)
            if a == -1:
                # If we can't extract a right window, leave placeholder empty scope
                out.append({"id": sid if sid else "BIP_G_CORE", "scope": "", "start": -1, "end": -1})
                continue
            span = normalize_spaces(text[a:b])
            out.append({"id": sid if sid else "BIP_G_CORE", "scope": span, "start": a, "end": b})
        return dedup(out)


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
    print(f"DEBUG: max_tokens from rule = {max_tokens}")
    if not max_tokens:
        print("DEBUG: No max_token_gap, returning empty")
        return out
    try:
        max_tokens = int(max_tokens)
    except Exception:
        max_tokens = 8
    # Hard‑code the list of possible second parts; these mirror the YAML definition.
    part1_set = {"ne", "n'", "n’"}
    part2_set = {"pas", "plus", "jamais", "rien", "personne", "guère", "point", "nul"}
    existing_keys = {(c.get("id"), c.get("start"), c.get("end")) for c in existing_cues}
    used_part1_pos = set()
    used_part2_pos = set()
    for i, (tok, a, b) in enumerate(tokens):
        t = tok.lower()
        # un marqueur de début peut être "ne", ou bien un token débutant par "n'" ou "n’",
        # ou bien le token isolé "n" suivi d'un token apostrophe (tokenization split: 'n', "'")
        is_part1 = (
            t == "ne"
            or t.startswith("n'")
            or t.startswith("n’")
            or (t == "n" and i + 1 < len(tokens) and tokens[i + 1][0] in ["'", "’"])
        )
        if is_part1:
            # skip if this part1 token was already used to form a pair
            if a in used_part1_pos:
                continue
            # search ahead within max_tokens tokens (excluding punctuation tokens)
            gap = 0
            paired = False
            # Si c'est une contraction "n" + "'", commencer la recherche après l'apostrophe
            start_search = i + 2 if (t == "n" and i + 1 < len(tokens) and tokens[i + 1][0] in ["'", "'"]) else i + 1
            
            # determine stop punctuation for this rule (fallback to default)
            stop_punct = set((rule.get('options') or {}).get('stop_punct') or DEFAULT_STOP_PUNCT)
            for j in range(start_search, len(tokens)):
                t2, a2, b2 = tokens[j]
                # If token is punctuation and in configured stop_punct, stop searching further
                if re.match(PUNCT_RE, t2):
                    if t2 in stop_punct:
                        break
                    # otherwise ignore it but don't count as gap
                    continue
                gap += 1
                if gap > max_tokens:
                    break
                if t2.lower() in part2_set:
                    # ensure we don't already have this cue
                    # Forme la clé avec les vraies positions 
                    # skip if this part2 token was already used
                    if b2 in used_part2_pos:
                        break
                    key = (rule.get("id"), a, b2)
                    if key not in existing_keys:
                        # Found a valid pair: build pair cue
                        # Extract tokens and preserve exact forms
                        part1_tok = tokens[i][0]
                        part2_tok = tokens[j][0]

                        # Rebuild part1_text and compute p1 spans (handle 'n' + apostrophe tokenization)
                        if part1_tok == 'n' and i + 1 < len(tokens) and tokens[i + 1][0] in ["'", "’"]:
                            part1_text = "n" + tokens[i + 1][0]
                            p1_start = tokens[i][1]
                            p1_end = tokens[i + 1][2]
                        else:
                            part1_match = re.match(r"(?i)^(ne|n['’]?)", part1_tok)
                            if part1_match:
                                part1_text = part1_match.group(0)
                                p1_start = tokens[i][1] + part1_match.start()
                                p1_end = tokens[i][1] + part1_match.end()
                            else:
                                part1_text = part1_tok
                                p1_start = tokens[i][1]
                                p1_end = tokens[i][2]

                        part2_match = re.match(r"(?i)^(pas|plus|jamais|rien|personne|guère|guere|point|nul)", part2_tok)
                        if part2_match:
                            part2_text = part2_match.group(0)
                        else:
                            part2_text = part2_tok

                        label = (part1_text + " " + part2_text).strip()
                        cue_start = a
                        cue_end = b2

                        out.append({
                            "id": rule.get("id", "NE_BIPARTITE_EXTENDED"),
                            "cue_label": label,
                            "start": cue_start,
                            "end": cue_end,
                            "group": rule.get("group", "bipartite")
                        })
                        # mark these token spans as used so we don't re-pair them
                        used_part1_pos.add(a)
                        used_part2_pos.add(b2)
                    # once we've attempted a pairing for this part1 token, move to next part1
                    paired = True
                    break
            # if we scanned ahead and DID NOT pair this part1 with any part2, emit single-left particle
            if not paired:
                # compute part1_text and spans as above
                part1_tok = tokens[i][0]
                if part1_tok == 'n' and i + 1 < len(tokens) and tokens[i + 1][0] in ["'", "’"]:
                    part1_text = "n" + tokens[i + 1][0]
                    p1_start = tokens[i][1]
                    p1_end = tokens[i + 1][2]
                else:
                    part1_match = re.match(r"(?i)^(ne|n['’]?)", part1_tok)
                    if part1_match:
                        part1_text = part1_match.group(0)
                        p1_start = tokens[i][1] + part1_match.start()
                        p1_end = tokens[i][1] + part1_match.end()
                    else:
                        part1_text = part1_tok
                        p1_start = tokens[i][1]
                        p1_end = tokens[i][2]
                single_key = (rule.get("id"), p1_start, p1_end)
                if single_key not in existing_keys and p1_start is not None:
                    out.append({
                        "id": rule.get("id", "NE_BIPARTITE_EXTENDED"),
                        "cue_label": part1_text,
                        "start": p1_start,
                        "end": p1_end,
                        "group": rule.get("group", "bipartite")
                    })
                # mark part1 as used so we don't emit again
                used_part1_pos.add(a)
    return out

# ----------------- contrat LLM -----------------
# LLM-related hints removed for deterministic-only mode.


# LLM contract removed: this runner is deterministic-only and does not build
# or attach any LLM prompts or instructions. Any orchestration for LLMs should
# be documented in an external `orchestrator.md` and handled outside this script.

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

def annotate_sentence(text: str, sid: int, markers_by_group, strategies_by_id, order_by_group) -> Dict[str,Any]:
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

    # Scopes generation removed: scope extraction and QC are delegated to the
    # LLM / post-processing step. We no longer compute group_scopes or scopes
    # here to keep this runner deterministic and focused on cue detection.

    obj = {
        "id": sid,
        "text": text,
        "pipeline_step": "STEP1_DETERMINISTIC",
        "candidates_rules_ID_cues": build_candidates_rules_id_cues(groups_present, markers_by_group),
        "cues": cues
    }
    return obj

# ----------------- CLI -----------------

def main():
    ap = argparse.ArgumentParser(description="Runner permissif v3 (no-NLP, pipeline renforcé)")
    ap.add_argument("--rules", required=True, help="Chemin dossier rules/")
    ap.add_argument("--input", required=True, help="Fichier texte (1 phrase/ligne)")
    ap.add_argument("--output", required=True, help="Sortie JSONL")
    # removed --mode/LLM flags: runner is deterministic-only
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
            if not text:
                continue
            sid += 1
            obj = annotate_sentence(text, sid, markers_by_group, strategies_by_id, order_by_group)
            # Write a minimal JSON object: only id, text and cues (user requested)
            minimal = {"id": obj.get("id"), "text": obj.get("text"), "cues": obj.get("cues", [])}
            fout.write(json.dumps(minimal, ensure_ascii=False) + "\n")
    log.info("Terminé: %d phrases → %s", sid, args.output)

if __name__ == "__main__":
    main()