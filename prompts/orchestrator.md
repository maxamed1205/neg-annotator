# Orchestrateur d'annotation (pipeline 0→7)

## But
Fournir une description concise et exécutable de la pipeline d'annotation pilotée par les règles dans `rules/` et utilisable soit localement (scripts Python) soit via un LLM (payload prédéfini). Ce document décrit les passes, les contraintes fortes et les commandes PowerShell recommandées.

## Principes clés
- Respect strict des règles contenues dans `rules/*.yaml` (marqueurs, portées, exceptions, validations).
- Deux sorties intermédiaires distinctes : `data/predictions.jsonl` (sortie brute IA) puis `data/annotations.jsonl` (fichier final construit et validé).
- Ne jamais écraser `data/annotations.jsonl` : append uniquement après validation.
- Indices : caractères 0-based `[start, end)` sur le texte normalisé. Conserver mapping original↔normalisé.

## Pipeline (par phrase)
- Pass 0 — Normalisation
  - Appliquer `rules/00_normalization.yaml` pour produire `norm_text` et le mapping d'offsets.

- Pass 1 — Détection des cues (marqueurs)
  - Utiliser `rules/10_markers/*.yaml` pour détecter tous les marqueurs candidats (ex. `sans`, `ne ... pas`, `aucun`, `ni`, locutions, lexical).
  - Rendre, pour chaque cue, le texte et la position dans le texte normalisé.

- Pass 2 — Construction des scopes
  - Appliquer `rules/20_scopes/*.yaml` (stratégies GN complet, support+entité pour `sans`, coordination, fallbacks, meta_heads).
  - Produire pour chaque scope le texte et les indices dans `norm_text` (sans inclure le cue).

- Pass 3 — Exceptions & locutions figées
  - Appliquer `rules/40_exceptions.yaml` (phrases figées, gardes lexicographiques, restrictions comme `hormis/sauf`).

- Pass 4 — Polarité
  - Déduire la polarité via `rules/30_polarity.yaml` (NEGATIVE / POSITIVE / NEUTRAL / MIXED). Prendre en compte normalité et tokens de garde.

- Pass 5 — Prédictions IA (optionnel / obligatoire si on utilise un LLM)
  - L'IA génère `data/predictions.jsonl` contenant pour chaque phrase: id, text, cues_pred (list), scopes_pred (list of lists), polarity_pred, et champs de diagnostic (optionnel).

- Pass 6 — Construction des annotations finales
  - `tools/build_annotations.py` transforme `data/predictions.jsonl` → `data/annotations.jsonl` : recherche des offsets, construction du mapping cue↔scope(s), normalisation finale des champs.

- Pass 7 — Validation / Réparation
  - `tools/validate.py` applique les checks définis (voir `rules/60_validation_checks.yaml`) et signale/fixe les erreurs (ex.: scope contenant un cue, indices hors bornes, scope vide).
  - Réparer automatiquement quand possible, sinon émettre un rapport et ne pas append.

## Format attendu
- Le fichier final `data/annotations.jsonl` est une ligne JSON par phrase. Le validateur `tools/validate.py` définit les contraintes et doit être vert avant append.
- Encodage : UTF-8 ; sérialisation : `json.dumps(obj, ensure_ascii=False)`.

## Contraintes fortes (rappel)
- Jamais de verbe comme partie du cue.
- Aucun marqueur dans le scope.
- `ni ... ni ...` : policy multi‑scopes ou scope partagé selon règle appliquée.
- Cooccurrence `aucun + ne pas` : appliquer la priorité/règle prévue dans `rules/`.

## LLM & workflow recommandé

Fournir au LLM un contexte structuré et exécuter un pipeline découplé : LLM → `data/predictions.jsonl` → `tools/build_annotations.py` → `tools/validate.py` → append vers `data/annotations.jsonl` uniquement si tout est vert.

- Contexte à fournir au LLM :
  - system prompt minimal et instructions précises (utiliser `prompts/llm_multi_pass_template.md`).
  - le résumé compact `prompts/rules_summary.json` (facultatif mais utile) ou extraits ciblés de `rules/*.yaml` quand nécessaire.
  - 1–3 exemples few-shot : `prompts/fewshot_multi_pass.jsonl`.

- Format attendu de sortie LLM (obligatoire)
  - Le LLM produit `data/predictions.jsonl` (une ligne JSON par phrase). Chaque ligne doit contenir au minimum :
    - `id` (integer),
    - `text` (original or normalized text used by the LLM),
    - `cues_pred` : liste de chaînes (les marqueurs détectés),
    - `scopes_pred` : liste de listes de chaînes (chaque scope en tant que texte ou tokens),
    - `polarity_pred` : chaîne (NEGATIVE / POSITIVE / NEUTRAL / MIXED),
    - (optionnel) champs diagnostics pour faciliter le debug.
  - IMPORTANT : le LLM n'écrit pas directement `data/annotations.jsonl`.

- Pourquoi ce découpage :
  - Permet d'inspecter et corriger les prédictions brutes.
  - Évite d'écraser les annotations validées.
  - Rend le pipeline reproductible et auditable.

## Exemple PowerShell (flux recommandé)
```powershell
# 1) Générer predictions.jsonl via votre LLM (assemblez payload = template + rules_summary + fewshots)
#    (la commande exacte dépend du fournisseur API ; envoyez le payload et stockez la réponse dans data/predictions.jsonl)

# 2) Construire annotations finales (cherche offsets, construit mapping cue<->scope)
python tools/build_annotations.py data/predictions.jsonl --out data/annotations.jsonl

# 3) Valider
python tools/validate.py data/annotations.jsonl

# 4) Si tout est vert, append manuellement (ou via script) dans l'archive finale
#    (ne jamais écraser le fichier existant)
# Exemple d'append sûr en PowerShell :
Get-Content data/annotations.jsonl | Out-File -FilePath data/annotations_master.jsonl -Encoding utf8
Get-Content data/annotations.jsonl -Raw | Add-Content -Path data/annotations_master.jsonl -Encoding utf8
```

## Bonnes pratiques
- Garder le workflow découplé (LLM → predictions → build → validate) pour pouvoir inspecter et réparer.
- Fournir au LLM un `rules_summary.json` ciblé plutôt que des YAML entiers si la taille du contexte est critique.
- Ajouter few-shots pertinents quand vous modifiez des familles de règles.
- Versionner `rules/*.yaml`, `prompts/*` et `data/predictions.jsonl` pour traçabilité.

## Notes opérationnelles
- Si vous recréez ou modifiez un schéma de sortie, adaptez `tools/build_annotations.py` et `tools/validate.py` en conséquence.
- Conserver les indices en caractères 0-based `[start, end)` sur le texte normalisé et stocker le mapping original↔normalisé pour retrouver facilement les spans dans le texte original.