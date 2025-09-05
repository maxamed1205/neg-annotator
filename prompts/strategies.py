from __future__ import annotations
import re
from typing import List, Dict, Any
import regex as reg
from .tokenize import window_right, normalize_spaces, strip_leading_de, DEFAULT_STOP_PUNCT, DEFAULT_STOP_LEXEMES, PUNCT_RE


def guard_deny_if_surface(strategy: Dict[str,Any], text: str) -> bool:
    cfg = (strategy.get("guards") or {}).get("deny_if_surface")
    if not cfg:
        return False
    for g in cfg:
        pat = g.get("pattern") if isinstance(g, dict) else g
        if not pat:
            continue
        flags = reg.IGNORECASE if (isinstance(g, dict) and ((g.get("options") or {}).get("case_insensitive"))) else 0
        rx = reg.compile(pat, flags)
        if rx.search(text):
            return True
    return False


def _local_dedup(spans: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    seen = set(); out = []
    for s in spans:
        key = (s.get("id"), s.get("start"), s.get("end"), s.get("role"))
        if key in seen:
            continue
        seen.add(key); out.append(s)
    return out


def exec_strategy(group: str, sid: str, strat: Dict[str,Any], text: str, tokens,
                  cues_for_group: List[Dict[str,Any]], all_group_scopes: Dict[str,List[Dict[str,Any]]]) -> List[Dict[str,Any]]:
    stype = strat.get("scope_strategy") or ""
    opts = strat.get("options") or {}

    if guard_deny_if_surface(strat, text):
        return []

    # SKIP_IF_PATTERN
    if stype == "SKIP_IF_PATTERN":
        pat = (opts or {}).get("pattern")
        if pat and re.search(pat, text):
            return [{"_skip_group": group, "strategy": sid}]
        return []

    # SKIP_IF_LEXICALIZED
    if stype == "SKIP_IF_LEXICALIZED":
        patterns = (opts or {}).get("lexicalized_patterns", [])
        for p in patterns:
            if re.search(rf"\b{re.escape(p)}\b", text, flags=re.IGNORECASE):
                return [{"_skip_group": group, "strategy": sid}]
        return []

    # NEP_SMART (bipartite core)
    if stype == "NEP_SMART" or (sid.endswith("_CORE") and group=="bipartite"):
        out = []
        max_tokens = int((strat.get("options") or {}).get("max_token_gap", 8))
        stop_punct = (strat.get("options") or {}).get("stop_punct") or DEFAULT_STOP_PUNCT
        stop_lexemes = (strat.get("options") or {}).get("stop_lexemes") or DEFAULT_STOP_LEXEMES
        for c in cues_for_group:
            a,b = window_right(tokens, c["end"], max_tokens, stop_punct, stop_lexemes)
            if a == -1:
                out.append({"id": sid if sid else "BIP_G_CORE", "scope": "", "start": -1, "end": -1})
                continue
            span = normalize_spaces(text[a:b])
            out.append({"id": sid if sid else "BIP_G_CORE", "scope": span, "start": a, "end": b})
        return _local_dedup(out)

    # DET_NEG_GN_SMART
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
        return _local_dedup(out)

    # PREP cores
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
        return _local_dedup(out)

    # NI coord
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
        return _local_dedup(out)

    # COOC_DET_RESOLVE
    if stype == "RESOLVE_COOCURRENCE" or sid.endswith("COOC_DET_RESOLVE"):
        out=[]
        bip = all_group_scopes.get("bipartite", [])
        det = all_group_scopes.get("determinant", [])
        for b1 in bip:
            for d1 in det:
                if b1.get("start") is None or d1.get("start") is None:
                    continue
                # use simple overlap fraction
                a = max(b1["start"], d1["start"]) ; c = min(b1["end"], d1["end"])
                inter = max(0, c - a)
                den = max(b1["end"], d1["end"]) - min(b1["start"], d1["start"])
                if den>0 and inter/den >= 0.5:
                    a = min(b1["start"], d1["start"]) ; c = max(b1["end"], d1["end"])
                    out.append({"id": sid, "scope": normalize_spaces(text[a:c]), "start": a, "end": c})
        return _local_dedup(out)

    # GOVERNOR_SUPPORT_AUTO
    if stype == "GOVERNOR_SUPPORT_AUTO":
        out=[]
        for pre in ["selon","d'après","d’\u2009après","conformément à","au regard de","en accord avec","par"]:
            m_iter = re.finditer(rf"\b{re.escape(pre)}\b\s+([^.,;:]+)", text, flags=re.IGNORECASE)
            for m in m_iter:
                a = m.start(1); b = m.end(1)
                out.append({"id": sid, "role": "support", "scope": normalize_spaces(text[a:b]), "start": a, "end": b})
        m = re.search(r"(^|[\n\.])([^\n:\.]{3,})\s*:[\s\-–—]*$", text)
        if m:
            a = m.start(2); b = m.end(2)
            out.append({"id": sid, "role": "support", "scope": normalize_spaces(text[a:b]), "start": a, "end": b})
        return _local_dedup(out)

    # Fallback when_pattern
    wpat = strat.get("when_pattern")
    if wpat:
        flags = reg.IGNORECASE if (strat.get("options") or {}).get("case_insensitive") else 0
        rx = reg.compile(wpat, flags)
        out=[]
        for m in rx.finditer(text):
            a,b = m.start(), m.end()
            out.append({"id": sid, "scope": normalize_spaces(text[a:b]), "start": a, "end": b})
        return _local_dedup(out)

    return []


__all__ = ["exec_strategy", "guard_deny_if_surface"]
