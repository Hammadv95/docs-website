p="main.py"
lines=open(p,"r",encoding="utf8").read().splitlines()

out=[]
in_meili_block=False

for line in lines:
    if line.startswith("await meili_upsert({"):
        in_meili_block=True
        out.append("    " + line)  # indent into function
        continue

    if in_meili_block:
        # keep indenting until we hit the closing "})"
        out.append("    " + line)
        if line.strip() == "})":
            in_meili_block=False
        continue

    out.append(line)

open(p,"w",encoding="utf8").write("\n".join(out) + "\n")
print("✅ Fixed meili_upsert indentation block")
