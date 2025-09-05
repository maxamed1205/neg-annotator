from __future__ import annotations
from typing import List, Dict, Any
from .tokenize import normalize_spaces


def spans_overlap(x: Dict[str,Any], y: Dict[str,Any]) -> float:
    a1,a2 = x.get("start", -1), x.get("end", -1)
    b1,b2 = y.get("start", -1), y.get("end", -1)
    if a1<0 or a2<0 or b1<0 or b2<0:
        return 0.0
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
        if s.get("start", -1) >= 0 and s.get("end", -1) >= 0:
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


__all__ = ["dedup", "apply_qc", "qc_trim_appositions", "spans_overlap"]
