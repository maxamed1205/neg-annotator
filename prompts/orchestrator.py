# orchestrator.py
"""
Orchestrateur complet (VSCode Agent):
1) Exécute runner.py → génère annotations_step1.jsonl
2) Pour chaque objet, construit prompt LLM (SYSTEM+USER)
3) Appelle directement l'agent/model configuré dans VSCode
4) Sauvegarde la sortie JSON finale dans annotations_llm.jsonl
"""

import json
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
from prompts.llm_prompt import build_llm_prompt

# --- chemins ---
# Détermine le dossier racine du projet de façon portable. Si tu exécutes ce
# fichier via « python orchestrator.py … », ROOT correspondra au dossier parent
# contenant « prompts » et « rules ».

RULES = ROOT / "rules"
DATA = ROOT / "data"
PROMPTS = ROOT / "prompts"

INPUT = DATA / "corpus_raw" / "example.txt"
STEP1 = DATA / "annotations_step1.jsonl"
STEP2 = DATA / "annotations_llm.jsonl"

# --- 1. Lancer runner.py pour générer STEP1 ---
print("[INFO] Étape 1 : exécution runner.py")
subprocess.run([
    "python", str(PROMPTS / "runner.py"),
    "--rules", str(RULES),
    "--input", str(INPUT),
    "--output", str(STEP1),
    "--mode", "permissive"
], check=True)

# --- 2. Lire STEP1 et envoyer au modèle (via VSCode Agent) ---
print("[INFO] Étape 2 : envoi des phrases au LLM (via agent VSCode)")

with open(STEP1, encoding="utf-8") as fin, open(STEP2, "w", encoding="utf-8") as fout:
    for line in fin:
        obj = json.loads(line)

        # Construire prompts
        system_prompt, user_prompt = build_llm_prompt(obj, rules_dir=str(RULES))

        # Ici au lieu d'appeler l'API OpenAI, tu utilises la commande/extension
        # VSCode agent fournit un "invoke" du modèle actif
        # Exemple pseudo-code (dépend de ton extension agent) :
        #
        # response = agent.invoke([
        #     {"role": "system", "content": system_prompt},
        #     {"role": "user", "content": user_prompt}
        # ])
        #
        # out_str = response["content"]

        # Pour l’instant je mets un placeholder :
        out_str = "{}"  # <-- l'agent doit renvoyer la sortie JSON

        try:
            parsed = json.loads(out_str)
        except json.JSONDecodeError:
            print("[WARN] Sortie LLM non-JSON, skip:", out_str[:200])
            continue

        fout.write(json.dumps(parsed, ensure_ascii=False) + "\n")

print(f"[OK] Fichier final écrit → {STEP2}")
