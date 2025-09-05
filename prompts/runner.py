"""Minimal CLI wrapper delegating to prompts.detector.annotate_sentence.

Kept intentionally small for testability.
"""

from __future__ import annotations
import argparse
import json
import logging
from pathlib import Path

from .detector import load_markers, load_registry_and_scopes, annotate_sentence


def make_logger(level: str = "INFO") -> logging.Logger:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
    return logging.getLogger("prompts.runner")

# def normalize_text_for_regex(text: str) -> str:
#     import unicodedata
#     text = text.replace("’", "'")      # normalise les apostrophes
#     text = text.lower()                 # minuscule pour faciliter les regex
#     text = unicodedata.normalize('NFC', text)  # Unicode standard
#     return text
    
def main() -> None:
    ap = argparse.ArgumentParser(description="Runner permissif v3 (no-NLP, pipeline renforcé)")
    ap.add_argument("--rules", required=True, help="Chemin dossier rules/")
    ap.add_argument("--input", required=True, help="Fichier texte (1 phrase/ligne)")
    ap.add_argument("--output", required=True, help="Sortie JSONL")
    ap.add_argument("--log", default="INFO")
    args = ap.parse_args()

    log = make_logger(args.log)

    rules_dir = Path(args.rules)
    markers_by_group = load_markers(rules_dir)
    strategies_by_id, order_by_group = load_registry_and_scopes(rules_dir)

    sid = 0
    with open(args.input, "r", encoding="utf-8") as fin, open(args.output, "w", encoding="utf-8") as fout:
        for line in fin:
            text = line.strip()
            if not text:
                continue
            sid += 1
            seen_intervals = []  # ← réinitialisation ici
            # normalized_text = normalize_text_for_regex(text)
            # obj = annotate_sentence(text, sid, markers_by_group, strategies_by_id, order_by_group)
            obj = annotate_sentence(text, sid, markers_by_group, strategies_by_id, order_by_group, seen_intervals)
            minimal = {"id": obj.get("id"), "text": obj.get("text"), "cues": obj.get("cues", [])}
            # cue_ids = [c["id"] for c in minimal["cues"]]
            # print(f"Sentence {sid} cue IDs: {cue_ids}")
            fout.write(json.dumps(minimal, ensure_ascii=False) + "\n")
    log.info("Terminé: %d phrases → %s", sid, args.output)


if __name__ == "__main__":
    main()
