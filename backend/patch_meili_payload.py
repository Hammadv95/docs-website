import re

p="main.py"
s=open(p,"r",encoding="utf8").read()

# Locate meili_search function block
m=re.search(r"async def meili_search\([^)]*\):", s)
if not m:
    raise SystemExit("meili_search not found")

start=m.start()
end=s.find("\nasync def ", start+1)
if end == -1:
    end=len(s)

block=s[start:end]

# Force payload to {"q": q, "limit": limit}
block=re.sub(r"payload\s*=\s*\{.*?\}\s*", 'payload = {"q": q, "limit": limit}\n', block, flags=re.S)

# If payload didn't exist, insert it before the request
if 'payload = {"q": q, "limit": limit}' not in block:
    block=re.sub(r"(async with httpx\.AsyncClient\(.*?\)\s+as client:\s*\n\s*)(r\s*=\s*await client\.)",
                 r'\1payload = {"q": q, "limit": limit}\n        \2', block, flags=re.S)

# Ensure request uses json=payload (not data=payload)
block=re.sub(r"json\s*=\s*\{.*?\}", "json=payload", block, flags=re.S)
block=re.sub(r"data\s*=\s*payload", "json=payload", block)

# Replace raise_for_status with readable Meili error
block=block.replace("r.raise_for_status()", "if r.status_code >= 400:\n            raise HTTPException(status_code=500, detail=f\"Meili error {r.status_code}: {r.text}\")")

s2=s[:start]+block+s[end:]
open(p,"w",encoding="utf8").write(s2)
print("✅ Patched meili_search payload to use {q, limit} and added readable errors")
