import re

text = "Aucune anomalie n'a été trouvée, le bilan ne montre plus d'élévation enzymatique, et on n'a noté aucune rechute ni complication."

print("Phrase:")
print(text)
print()

# Pattern de NE_ELLIPTIQUE_VERBAL
pattern = r"(?i)(?P<part1>\bn['']|\bne)\s+\w+"

print("Pattern NE_ELLIPTIQUE_VERBAL:")
print(pattern)
print()

matches = list(re.finditer(pattern, text))
print(f"Matches found: {len(matches)}")
print()

for i, m in enumerate(matches):
    print(f"Match {i+1}: '{m.group()}' at {m.start()}-{m.end()}")
    try:
        print(f"  part1: '{m.groupdict().get('part1', 'N/A')}'")
    except:
        print("  part1: N/A")
    print()

# Testons aussi le pattern exact du YAML
yaml_pattern = r"(?i)(?P<part1>\\bn['']|\\bne)\\s+\\w+"
print("Pattern YAML original:")
print(yaml_pattern)

# Clean pattern (comme fait par le code)
clean_pattern = yaml_pattern.replace('\\\\', '\\')
print("Pattern après cleaning:")
print(clean_pattern)

matches2 = list(re.finditer(clean_pattern, text))
print(f"Matches avec pattern nettoyé: {len(matches2)}")
for i, m in enumerate(matches2):
    print(f"Match {i+1}: '{m.group()}' at {m.start()}-{m.end()}")
