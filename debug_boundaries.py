text = "Aucune anomalie n'a été trouvée, le bilan ne montre plus d'élévation enzymatique, et on n'a noté aucune rechute ni complication."

print("Analyse caractère par caractère:")
print()

# Première occurrence de n'a
pos1 = text.find("n'a")
print(f"Première 'n'a' à position {pos1}:")
print(f"Contexte: '{text[pos1-5:pos1+8]}'")
print("Caractères individuels:")
for i in range(pos1-3, pos1+5):
    if 0 <= i < len(text):
        char = text[i]
        marker = "← n'a start" if i == pos1 else ""
        print(f"  {i}: '{char}' ({ord(char)}) {marker}")
print()

# Deuxième occurrence de n'a  
pos2 = text.find("n'a", pos1+1)
print(f"Deuxième 'n'a' à position {pos2}:")
print(f"Contexte: '{text[pos2-5:pos2+8]}'")
print("Caractères individuels:")
for i in range(pos2-3, pos2+5):
    if 0 <= i < len(text):
        char = text[i]
        marker = "← n'a start" if i == pos2 else ""
        print(f"  {i}: '{char}' ({ord(char)}) {marker}")
print()

# Test du pattern avec \b
import re
pattern_with_boundary = r"\bn'a"
matches = list(re.finditer(pattern_with_boundary, text))
print(f"Pattern avec \\b: '{pattern_with_boundary}' trouve {len(matches)} matches")

# Test sans \b
pattern_without_boundary = r"n'a"
matches2 = list(re.finditer(pattern_without_boundary, text))
print(f"Pattern sans \\b: '{pattern_without_boundary}' trouve {len(matches2)} matches")
for i, m in enumerate(matches2):
    print(f"  Match {i+1}: '{m.group()}' at {m.start()}-{m.end()}")
