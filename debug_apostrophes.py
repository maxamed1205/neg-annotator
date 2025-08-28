import re

text = "Aucune anomalie n'a été trouvée, le bilan ne montre plus d'élévation enzymatique, et on n'a noté aucune rechute ni complication."

print("Test du pattern exact NE_ELLIPTIQUE_VERBAL:")
print()

# Pattern exact du YAML
yaml_pattern = r"(?i)(?P<part1>\\bn['']|\\bne)\\s+\\w+"
print(f"Pattern YAML: {yaml_pattern}")

# Nettoyage comme fait par le code
clean_pattern = yaml_pattern.replace('\\\\b', '\\b').replace('\\\\s', '\\s').replace('\\\\w', '\\w')
print(f"Pattern nettoyé: {clean_pattern}")

# Test avec différentes variantes
patterns_to_test = [
    r"(?i)(?P<part1>\bn['']|\bne)\s+\w+",
    r"(?i)(?P<part1>\bn[''']|\bne)\s+\w+", 
    r"(?i)(?P<part1>\bn['']|\bne)\s+\w+",
    r"(?i)(?P<part1>\bn['\u2019]|\bne)\s+\w+"
]

for i, pattern in enumerate(patterns_to_test):
    print(f"\nPattern {i+1}: {pattern}")
    try:
        matches = list(re.finditer(pattern, text))
        print(f"  Matches: {len(matches)}")
        for j, m in enumerate(matches):
            print(f"    Match {j+1}: '{m.group()}' at {m.start()}-{m.end()}")
            print(f"    part1: '{m.groupdict().get('part1', 'N/A')}'")
    except Exception as e:
        print(f"  Error: {e}")

# Testons spécifiquement les apostrophes
print(f"\nAnalyse des apostrophes dans le texte:")
for i, char in enumerate(text):
    if char in ["'", "'", "'"]:
        print(f"Position {i}: '{char}' (ord={ord(char)})")
