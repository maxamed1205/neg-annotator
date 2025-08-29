import json

# Charger les données d'annotations
with open("data/annotations_step1.jsonl", "r", encoding="utf-8") as f:
    annotations = [json.loads(line) for line in f]

# Charger les règles de portée
rules = {
    "bipartite": "rules/20_scopes/bipartites.yaml",
    "determinant": "rules/20_scopes/determinant.yaml",
    "preposition": "rules/20_scopes/preposition.yaml",
    "lexical": "rules/20_scopes/lexical.yaml",
    "locution": "rules/20_scopes/locutions.yaml",
}

# Fonction pour appliquer les règles
# (Simplifiée pour cet exemple, à compléter selon les règles YAML)
def apply_rules(annotation, rules):
    scopes = []
    for cue in annotation["cues"]:
        group = cue["group"]
        rule_file = rules.get(group)
        if rule_file:
            # Charger et appliquer les règles pertinentes (simplifié)
            scope = {
                "id": "RULE_APPLIED",
                "scope_label": annotation["text"],
                "start": cue["end"],
                "end": len(annotation["text"]),
                "group": group,
            }
            scopes.append(scope)
        else:
            # Portée de secours
            scopes.append({
                "id": "LLM_FALLBACK_SCOPE",
                "scope_label": annotation["text"],
                "start": cue["end"],
                "end": len(annotation["text"]),
                "group": group,
            })
    return scopes

# Appliquer les règles à chaque annotation
results = []
for annotation in annotations:
    scopes = apply_rules(annotation, rules)
    annotation["scopes"] = scopes
    results.append(annotation)

# Sauvegarder les résultats
with open("data/annotations_with_scopes.jsonl", "w", encoding="utf-8") as f:
    for result in results:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

print("Traitement terminé. Résultats sauvegardés dans data/annotations_with_scopes.jsonl.")
