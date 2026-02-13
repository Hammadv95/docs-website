import re

p="main.py"
s=open(p,"r",encoding="utf8").read().splitlines(True)

out=[]
in_fn=False
patched=False

for line in s:
    if line.startswith("async def meili_search("):
        in_fn=True
        out.append(line)
        continue

    if in_fn and line.startswith("async def "):
        in_fn=False
        out.append(line)
        continue

    if in_fn and (not patched) and ("json={" in line) and ('"q"' in line) and ('"limit"' in line):
        indent = re.match(r"^(\s*)", line).group(1)
        out.append(f'{indent}json={{"q": q, "limit": limit, "filter": "is_published = true"}},\n')
        patched=True
        continue

    out.append(line)

open(p,"w",encoding="utf8").write("".join(out))
print(f"✅ patched meili_search filter: {patched}")
