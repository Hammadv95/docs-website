p = "main.py"

with open(p, "r", encoding="utf8") as f:
    s = f.read()

# Remove the filter portion safely
s = s.replace('"filter": "is_published = true", ', "")
s = s.replace(', "filter": "is_published = true"', "")
s = s.replace('"filter": "is_published = true"', "")

with open(p, "w", encoding="utf8") as f:
    f.write(s)

print("✅ Removed Meili filter safely")
