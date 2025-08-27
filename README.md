# neg-annotator (FR medical negation annotation automatique)

## Démarrage rapide
1. Ouvre le dossier dans VS Code.
2. Lis `prompts/orchestrator.md`. Copie son contenu dans Copilot Chat (ou ton agent).
3. Mets quelques phrases dans `data/corpus_raw/example.txt`.
4. Demande à Copilot d'exécuter les **passes 0→6** et d'écrire dans `data/annotations.jsonl`.
5. Lance `python tools/validate.py data/annotations.jsonl` et corrige selon le rapport.

## Arborescence
neg-annotator/
├─ data/
│  ├─ corpus_raw/
│  └─ annotations.jsonl
├─ rules/
├─ prompts/
└─ tools/

## Notes
- Les règles reprennent les principes du plan d’action (markers, scopes, cooccurrences, normalité).
- `tools/validate.py` fait une validation basique sans dépendances externes.
- `tools/normalize.py` réalise une normalisation simple et sûre (offsets majoritairement préservés).
