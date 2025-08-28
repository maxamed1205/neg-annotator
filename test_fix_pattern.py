import re

text = "Aucune anomalie n'a été trouvée, le bilan ne montre plus d'élévation enzymatique, et on n'a noté aucune rechute ni complication."

print("Test de correction du pattern NE_ELLIPTIQUE_VERBAL:")
print()

# Pattern actuel (buggé)
current_pattern = r"(?i)(?P<part1>\bn['']|\bne)\s+\w+"

# Pattern corrigé - option 1
fixed_pattern1 = r"(?i)(?P<part1>\bn['']a|\bne)\s+\w+"

# Pattern corrigé - option 2 (plus permissif)
fixed_pattern2 = r"(?i)(?P<part1>\bn[''][aàe]|\bne)\s+\w+"

# Pattern corrigé - option 3 (encore plus permissif)
fixed_pattern3 = r"(?i)(?P<part1>\bn[''][\w]|\bne)\s+\w+"

patterns = [
    ("Actuel (buggé)", current_pattern),
    ("Corrigé v1 (n'a)", fixed_pattern1), 
    ("Corrigé v2 (n'a/n'à/n'e)", fixed_pattern2),
    ("Corrigé v3 (n'+lettre)", fixed_pattern3)
]

for name, pattern in patterns:
    print(f"\n{name}: {pattern}")
    try:
        matches = list(re.finditer(pattern, text))
        print(f"  Matches: {len(matches)}")
        for j, m in enumerate(matches):
            print(f"    Match {j+1}: '{m.group()}' at {m.start()}-{m.end()}")
            print(f"    part1: '{m.groupdict().get('part1', 'N/A')}'")
    except Exception as e:
        print(f"  Error: {e}")

# Mieux : séparons complètement les deux cas
print(f"\n=== Alternative: séparer n' et ne ===")
pattern_n_apostrophe = r"(?i)\bn[''][aàeiouèéêë]\s+\w+"
pattern_ne = r"(?i)\bne\s+\w+"

print(f"Pattern n'+voyelle: {pattern_n_apostrophe}")
matches1 = list(re.finditer(pattern_n_apostrophe, text))
print(f"  Matches: {len(matches1)}")
for j, m in enumerate(matches1):
    print(f"    Match {j+1}: '{m.group()}' at {m.start()}-{m.end()}")

print(f"Pattern ne: {pattern_ne}")
matches2 = list(re.finditer(pattern_ne, text))
print(f"  Matches: {len(matches2)}")
for j, m in enumerate(matches2):
    print(f"    Match {j+1}: '{m.group()}' at {m.start()}-{m.end()}")
