p="main.py"
lines=open(p,"r",encoding="utf8").read().splitlines(True)
out=[]
done=False

for line in lines:
    # Target the exact json payload line inside meili_search
    if (not done) and 'json={"q": q, "limit": limit}' in line.replace(" ", ""):
        # Preserve indentation but add filter
        indent = line.split("j",1)[0]  # everything before 'json='
        out.append(f'{indent}json={{"q": q, "limit": limit, "filter": "is_published = true"}},\n')
        done=True
    else:
        out.append(line)

open(p,"w",encoding="utf8").write("".join(out))
print("✅ Re-added is_published filter (patched:", done, ")")
