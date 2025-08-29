===SYSTEM PROMPT===
[MODE]
EXECUTION STRICTE — TU DOIS EXÉCUTER CE CONTRAT. NE PAS EXPLIQUER. NE PAS RÉSUMER. NE PAS POSER DE QUESTIONS.
TOUTE SORTIE EN DEHORS DU FORMAT DEMANDÉ EST INTERDITE.

[ENTRÉES]
- Règles (YAML) :
  C:\Users\maxam\Desktop\neg-annotator\rules\10_markers
  C:\Users\maxam\Desktop\neg-annotator\rules\20_scopes
- Corpus à annoter (JSONL) :
  C:\Users\maxam\Desktop\neg-annotator\data\annotations_step1.jsonl
- Sortie attendue (JSONL) :
  C:\Users\maxam\Desktop\neg-annotator\data\annotations.jsonl

[AGENT ACTIONS — À EXÉCUTER DANS CET ORDRE]
- lis C:\Users\maxam\Desktop\neg-annotator\rules\10_markers
- lis C:\Users\maxam\Desktop\neg-annotator\rules\20_scopes
- raisonnes
- modifies directement C:\Users\maxam\Desktop\neg-annotator\data\annotations_step1.jsonl
- ajoutes les portées
- NE PASSE PAS PAR UN FICHIER PYTHON

[CRITÈRES DE RÉUSSITE]
- Le fichier C:\Users\maxam\Desktop\neg-annotator\data\annotations.jsonl est créé.
- Chaque ligne contient {id, text, cues, scopes[]} avec les portées déduites selon les règles (ou fallback).
- Aucune explication ni résumé en sortie, uniquement l’output des commandes.
