from __future__ import annotations
import re
from typing import List, Tuple, Dict, Any
from .tokenize import PUNCT_RE, DEFAULT_STOP_PUNCT


def detect_bipartite_cross_tokens(text: str, tokens: List[Tuple[str,int,int]], existing_cues: List[Dict[str,Any]], rule: Dict[str,Any]) -> List[Dict[str,Any]]:
    out = []
    max_tokens = rule.get("options", {}).get("max_token_gap")
    if not max_tokens:
        return out
    try:
        max_tokens = int(max_tokens)
    except Exception:
        max_tokens = 8
    part1_set = {"ne", "n'", "n’"}
    part2_set = {"pas", "plus", "jamais", "rien", "personne", "guère", "point", "nul"}
    existing_keys = {(c.get("id"), c.get("start"), c.get("end")) for c in existing_cues}
    used_part1_pos = set()
    used_part2_pos = set()
    for i, (tok, a, b) in enumerate(tokens):
        t = tok.lower()
        is_part1 = (
            t == "ne"
            or t.startswith("n'")
            or t.startswith("n’")
            or (t == "n" and i + 1 < len(tokens) and tokens[i + 1][0] in ["'", "’"])
        )
        if is_part1:
            if a in used_part1_pos:
                continue
            gap = 0
            paired = False
            start_search = i + 2 if (t == "n" and i + 1 < len(tokens) and tokens[i + 1][0] in ["'", "'"]) else i + 1
            stop_punct = set((rule.get('options') or {}).get('stop_punct') or DEFAULT_STOP_PUNCT)
            for j in range(start_search, len(tokens)):
                t2, a2, b2 = tokens[j]
                if re.match(PUNCT_RE, t2):
                    if t2 in stop_punct:
                        break
                    continue
                gap += 1
                if gap > max_tokens:
                    break
                if t2.lower() in part2_set:
                    if b2 in used_part2_pos:
                        break
                    key = (rule.get("id"), a, b2)
                    if key not in existing_keys:
                        part1_tok = tokens[i][0]
                        part2_tok = tokens[j][0]
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
                        used_part1_pos.add(a)
                        used_part2_pos.add(b2)
                    paired = True
                    break
            if not paired:
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
                used_part1_pos.add(a)
    return out


__all__ = ["detect_bipartite_cross_tokens"]
