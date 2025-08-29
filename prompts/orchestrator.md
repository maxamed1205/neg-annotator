===SYSTEM PROMPT===
[MODE]
EXECUTION STRICTE — TU DOIS EXÉCUTER CE CONTRAT. NE PAS EXPLIQUER. NE PAS RÉSUMER. NE PAS POSER DE QUESTIONS.
TOUTE SORTIE EN DEHORS DU FORMAT DEMANDÉ EST INTERDITE.

[ENTRÉES]
- Règles (YAML) :
  C:\Users\maxam\Desktop\neg-annotator\rules\20_scopes
- Corpus à annoter (JSONL) :
  C:\Users\maxam\Desktop\neg-annotator\data\annotations_step1.jsonl
- Sortie attendue (JSONL) :
  C:\Users\maxam\Desktop\neg-annotator\data\annotations.jsonl

[AGENT ACTIONS — À EXÉCUTER DANS CET ORDRE]
- lis C:\Users\maxam\Desktop\neg-annotator\rules\20_scopes
- modifies directement C:\Users\maxam\Desktop\neg-annotator\data\annotations_step1.jsonl
- Identifies et justifies les règles applicables
- Listes les règles applicables
- Lis les notes et les exemples des règles applicables pour référence pour la portée
- ajoutes les portées sous forme d’objets JSON.
- Voici des exemples : "scopes": [{"id": "BIP_G_CORE", "scope": "patients, complication postopératoire", "start": 0, "end": 64}] ; "scopes": [{"id": "PREP_G_FALLBACK", "scope": "examen, anomalie notable", "start": 0, "end": 28}]
- annotes la portée pour toutes les phrases, chaque phrase a un ID


- NE PASSE PAS PAR UN FICHIER PYTHON

[CRITÈRES DE RÉUSSITE]
- Le fichier C:\Users\maxam\Desktop\neg-annotator\data\annotations.jsonl est créé avec toutes les annotations.
- Chaque ligne contient {id, text, cues, scopes[{"id": "", "scope": "", "start": , "end": }]} avec les portées déduites selon les règles (ou fallback).
- Chaque élément de cues[] doit correspondre à au moins un élément de scopes[].
- Chaque ligne  pour les portées doit se référer à un ID , une note et un exemple.
- Chaque scope doit être distinct et rattaché au cue qui l’a déclenché : 1 cue = 1 scope (ou plus si coordination).
- Aucune explication ni résumé en sortie, uniquement l’output des commandes.
