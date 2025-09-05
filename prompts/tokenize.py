from __future__ import annotations
import re
from typing import List, Tuple, Optional

# Tokenisation utils moved here for separation of concerns.
PUNCT_RE = r"[,;:!?\.()\[\]{}«»“”\"']"

DEFAULT_STOP_PUNCT = [",", ";", ":", ".", "!", "?", ""]
DEFAULT_STOP_LEXEMES = ["malgré", "mais", "cependant", "pourtant", "toutefois", "néanmoins"]


def tokenize_with_offsets(text: str) -> List[Tuple[str, int, int]]:
    # normalize typographic apostrophes to ASCII apostrophe so they are
    # recognized by the punctuation regex and tokenized consistently
    text = text.replace("’", "'").replace("\u2019", "'")
    toks: List[Tuple[str, int, int]] = []
    for m in re.finditer(r"\S+", text, flags=re.UNICODE):
        chunk = m.group(0)
        s = m.start()
        last = 0
        for pm in re.finditer(PUNCT_RE, chunk):
            if pm.start() > last:
                toks.append((chunk[last:pm.start()], s + last, s + pm.start()))
            toks.append((pm.group(0), s + pm.start(), s + pm.end()))
            last = pm.end()
        if last < len(chunk):
            toks.append((chunk[last:], s + last, s + len(chunk)))
    return [(t, a, b) for (t, a, b) in toks if t]


def window_right(tokens: List[Tuple[str, int, int]], start_char: int, max_tokens: int,
                 stop_punct: Optional[List[str]] = None,
                 stop_lexemes: Optional[List[str]] = None) -> Tuple[int, int]:
    stop = set(stop_punct or DEFAULT_STOP_PUNCT)
    cutters = {w.lower() for w in (stop_lexemes or DEFAULT_STOP_LEXEMES)}
    collected = []
    for tok, a, b in tokens:
        if a < start_char:
            continue
        if tok in stop:
            break
        if tok.lower() in cutters:
            break
        collected.append((a, b))
        if len(collected) >= max_tokens:
            break
    if not collected:
        return -1, -1
    return collected[0][0], collected[-1][1]


def strip_leading_de(span: str) -> str:
    return re.sub(r"^(?:de|d’|d')\s+", "", span, flags=re.IGNORECASE)


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()).replace("’", "'").replace("\u2019", "'")
