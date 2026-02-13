p="main.py"
lines=open(p,"r",encoding="utf8").read().splitlines(True)
out=[]
for l in lines:
    if 'return {"ok": True, "slug": doc_row["slug"], "url": f"/docs/{doc_row' in l:
        out.append('    return {"ok": True, "slug": doc_row["slug"], "url": f"/docs/{doc_row[\\'slug\\']}"}\n')
    else:
        out.append(l)
open(p,"w",encoding="utf8").write("".join(out))
print("fixed return indent (best-effort)")
