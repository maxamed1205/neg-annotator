import os
import json
from runner import annotate_sentence  # ton runner.py

# chemins
import argparse

default_corpus_path = os.path.join("data", "corpus_raw", "example.txt")
default_annotations_path = os.path.join("data", "annotations.jsonl")

parser = argparse.ArgumentParser(description="Annotate a corpus of sentences.")
parser.add_argument("--corpus", type=str, default=default_corpus_path, help="Path to the corpus file")
parser.add_argument("--annotations", type=str, default=default_annotations_path, help="Path to the annotations output file")
args = parser.parse_args()

corpus_path = args.corpus
annotations_path = args.annotations

# lire toutes les phrases
with open(corpus_path, "r", encoding="utf-8") as f:
    sentences = [line.strip() for line in f if line.strip()]

# vérifier si annotations.jsonl existe
mode = "a" if os.path.exists(annotations_path) else "w"

with open(annotations_path, mode, encoding="utf-8") as fout:
    for sid, text in enumerate(sentences, start=1):
        result = annotate_sentence(text)
        result["id"] = sid
        fout.write(json.dumps(result, ensure_ascii=False) + "\n")

print(f"Annotations ajoutées dans {annotations_path}")
