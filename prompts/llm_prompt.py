# llm_prompt.py
import json
import yaml
from pathlib import Path

SYSTEM_PROMPT = """Tu es un annotateur de négation clinique rigoureux.

Objectif : À partir d’une phrase + des règles de négation fournies (marqueurs et portées extraites des fichiers YAML) + le contrat LLM, produire un UNIQUE objet JSON valide (UTF-8, sans commentaire) qui contient :
- cues (avec id de règle),
- scopes (texte exact + offsets char 0-based [start, end[),
- rôles (subject | core | support | exception),
- polarité globale (NEGATIVE | AFFIRMATIVE | UNCERTAIN),
- mapping cue→scope par indices.

Contraintes cruciales :
- Tu dois t’appuyer sur les règles YAML données en entrée (10_markers et 20_scopes). Tu ne dois pas inventer d’IDs ou de stratégies.
- Si une règle YAML est présente dans pending_rules.rule_yaml, tu dois la relire et l’appliquer exactement.
- Si le runner a déjà proposé un scope ou un cue, garde-le en priorité et corrige seulement si manifestement faux.
- Respecte STRICTEMENT les offsets de caractères 0-based, end exclusif.
- N’inclus JAMAIS un verbe dans le cue.
- MUST_COMPLETE_MISSING : complète sujet et supports si absents ; ajoute les cues manquants (id 'LLM_FALLBACK', group 'inference') si un lexème évident est présent.
- Fusionne les scopes identiques et déduplique les doublons.
- Réponds UNIQUEMENT par le JSON demandé ; jamais de prose.
"""


def load_rules_for_groups(rules_dir: Path, groups: list[str]) -> dict:
    """Charge toutes les règles YAML de 10_markers et 20_scopes pour les groupes concernés"""
    out = {"markers": {}, "scopes": {}}

    # 10_markers
    for g in groups:
        folder = rules_dir / "10_markers"
        rules_for_group = []
        for f in folder.glob("*.yaml"):
            if g in f.name.lower():
                try:
                    items = yaml.safe_load(f.read_text(encoding="utf-8"))
                    if isinstance(items, list):
                        rules_for_group.extend(items)
                except Exception:
                    pass
        if rules_for_group:
            out["markers"][g] = rules_for_group

    # 20_scopes
    folder = rules_dir / "20_scopes"
    for f in folder.glob("*.yaml"):
        try:
            items = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(items, list):
                # garder seulement celles dont l'id correspond à ce groupe
                filtered = [s for s in items if g in (s.get("id","").lower())]
                if filtered:
                    out["scopes"].setdefault(g, []).extend(filtered)
        except Exception:
            pass

    return out


def build_llm_prompt(obj: dict, rules_dir: str) -> tuple[str, str]:
    all_groups = []
    for c in obj.get("cues", []):
        if isinstance(c["group"], list):
            all_groups.extend(c["group"])
        else:
            all_groups.append(c["group"])

    groups = sorted(set(all_groups))
    rules_full = load_rules_for_groups(Path(rules_dir), groups)

    slim = {
        "id": obj.get("id"),
        "text": obj.get("text"),
        "cues": obj.get("cues", []),
        "scopes": obj.get("scopes", []),
        "candidates_rules_ID_cues": obj.get("candidates_rules_ID_cues", []),
        "candidates_rules_ID_scopes": obj.get("candidates_rules_ID_scopes", []),
        "llm_contract": {
            k: obj["llm_contract"][k]
            for k in ["mode","policy","rules_obligations","hints","pending_rules"]
            if k in obj.get("llm_contract", {})
        },
        "rules_full": rules_full  # 🔥 Ajout : contenu YAML complet
    }

    user_prompt = (
        "[CONTEXTE]\n"
        "Tu reçois :\n"
        "1) La phrase à annoter\n"
        "2) Les candidats de règles (IDs par groupe) + stratégies de scopes par groupe\n"
        "3) Le contrat LLM (politique, hints, obligations) et les pending_rules à exécuter\n"
        "4) Des exemples few-shot par famille (voir plus bas)\n\n"

        "[DONNÉES]\n" +
        json.dumps(slim, ensure_ascii=False, indent=2) + "\n"
        "  # contient:\n"
        "  # - text\n"
        "  # - cues (détection déterministe)\n"
        "  # - scopes (propositions surface)\n"
        "  # - candidates_rules_ID_cues / candidates_rules_ID_scopes\n"
        "  # - llm_contract {policy, rules_obligations, hints, pending_rules[*].rule_yaml & cue & text}\n\n"

        "[INSTRUCTIONS]\n"
        "1) Lis et applique chaque pending_rules.rule_yaml au cue fourni (READ_AND_APPLY_RULE).\n"
        "2) Ajuste/complète les scopes selon les stratégies indiquées par groupe (registry).\n"
        "3) Ajoute les rôles :\n"
        "   - subject : sujet grammatical associé à la négation principale s’il est explicite\n"
        "   - core : prédicat ou GN/GV nié (la “portée cœur”)\n"
        "   - support : source/autorité (“selon…”, “d’après…”, titres à gauche avant ‘:’)\n"
        "   - exception : éléments exclusifs (“à l’exception de…”, “sauf…”)\n"
        "4) Fixe la polarité globale de la phrase (ou de l’assertion principale) : NEGATIVE / AFFIRMATIVE / UNCERTAIN.\n"
        "5) Sors un UNIQUE objet JSON conforme au SCHÉMA DE SORTIE ci-dessous.\n\n"

        "[SCHÉMA DE SORTIE — JSON]\n"
        "{\n"
        "  \"id\": {{id_du_runner}},\n"
        "  \"text\": \"{{phrase_originale}}\",\n"
        "  \"polarity\": \"NEGATIVE|AFFIRMATIVE|UNCERTAIN\",\n"
        "  \"cues\": [\n"
        "    {\"id\": \"RULE_ID\", \"group\": \"bipartite|determinant|preposition|conjonction|lexical|locution|adversative|inference\",\n"
        "     \"cue_label\": \"forme canonique\", \"start\": int, \"end\": int}\n"
        "  ],\n"
        "  \"scopes\": [\n"
        "    {\"id\": \"STRATEGY_ID|BIP_G_CORE|DET_G_CORE|PREP_GENERIC_CORE|CONJ_NI_CORE|...\",\n"
        "     \"scope\": \"texte exact\", \"start\": int, \"end\": int, \"role\": \"subject|core|support|exception\"}\n"
        "  ],\n"
        "  \"mapping\": [\n"
        "    {\"cue_index\": 0, \"scope_indices\": [0,2]}\n"
        "  ]\n"
        "}\n\n"

        "[FEW-SHOT — par famille]\n"
        "(Bipartite)\n"
        "- Ex.1\n"
        "  Texte : \"Le protocole n’a jamais été validé malgré plusieurs essais.\"\n"
        "  Sortie :\n"
        "  {\n"
        "    \"polarity\":\"NEGATIVE\",\n"
        "    \"cues\":[\n"
        "      {\"id\":\"NE_BIPARTITE_EXTENDED\",\"group\":\"bipartite\",\"cue_label\":\"ne jamais\",\"start\":13,\"end\":22},\n"
        "      {\"id\":\"PREP_MALGRÉ\",\"group\":\"preposition\",\"cue_label\":\"malgré\",\"start\":34,\"end\":40}\n"
        "    ],\n"
        "    \"scopes\":[\n"
        "      {\"id\":\"BIP_G_CORE\",\"scope\":\"Le protocole\",\"start\":0,\"end\":12,\"role\":\"subject\"},\n"
        "      {\"id\":\"BIP_G_CORE\",\"scope\":\"été validé\",\"start\":23,\"end\":33,\"role\":\"core\"},\n"
        "      {\"id\":\"PREP_MALGRÉ_CORE\",\"scope\":\"plusieurs essais\",\"start\":41,\"end\":57,\"role\":\"support\"}\n"
        "    ],\n"
        "    \"mapping\":[\n"
        "      {\"cue_index\":0,\"scope_indices\":[1]},\n"
        "      {\"cue_index\":1,\"scope_indices\":[2]}\n"
        "    ]\n"
        "  }\n"
        "- Ex.2\n"
        "  Texte : \"Le patient ne présente pas de fièvre.\"\n"
        "  → cue bipartite \"ne pas\"; scopes : subject=\"Le patient\", core=\"présente … fièvre\" (au minimum “fièvre” si tu restreins au GN nié). Polarité=NEGATIVE.\n\n"

        "(Determinant)\n"
        "- Ex.1\n"
        "  Texte : \"Aucune lésion n’a été retrouvée.\"\n"
        "  → cue determinant \"aucune\"; scopes : subject implicite (examen/constat) souvent omis, core=\"lésion\". Polarité=NEGATIVE.\n"
        "- Ex.2\n"
        "  Texte : \"Pas d’antécédents familiaux.\"\n"
        "  → cue determinant \"pas d’\"; core=\"antécédents familiaux\".\n\n"

        "(Préposition)\n"
        "- Ex.1\n"
        "  Texte : \"Examen réalisé sans complication notable.\"\n"
        "  → cue \"sans\"; core=\"complication notable\"; subject=\"Examen\". Polarité=NEGATIVE.\n"
        "- Ex.2\n"
        "  Texte : \"Hors de tout contexte infectieux.\"\n"
        "  → cue \"hors de\"; core=\"contexte infectieux\".\n\n"

        "(Conjonction — ni … ni …)\n"
        "- Ex.1\n"
        "  Texte : \"Le patient ne présente ni fièvre ni toux.\"\n"
        "  → cues \"ne …\" (bipartite) + \"ni\" (conj) ; cores multiples \"fièvre\", \"toux\"; subject=\"Le patient\".\n"
        "- Ex.2\n"
        "  Texte : \"Ni douleur, ni œdème.\"\n"
        "  → cores : \"douleur\", \"œdème\".\n\n"

        "(Lexical)\n"
        "- Ex.1\n"
        "  Texte : \"Traitement inefficace.\"\n"
        "  → cue lexical \"inefficace\"; core=\"Traitement\"; polarité=NEGATIVE (échec).\n"
        "- Ex.2\n"
        "  Texte : \"Résultat non concluant.\"\n"
        "  → cue lexical \"non\"; core=\"concluant\" (ou \"résultat non concluant\").\n\n"

        "(Locution / Exception)\n"
        "- Ex.1\n"
        "  Texte : \"À l’exception de la fièvre, tout est normal.\"\n"
        "  → cue \"à l’exception de\"; role=exception pour \"la fièvre\"; polarité AFFIRMATIVE globale mais exception marquée.\n"
        "- Ex.2\n"
        "  Texte : \"Sauf saignement actif.\"\n"
        "  → cue \"sauf\"; exception=\"saignement actif\".\n\n"

        "[FIN — RENDS UNIQUEMENT LE JSON DU SCHÉMA]\n"
    )

    return SYSTEM_PROMPT, user_prompt
