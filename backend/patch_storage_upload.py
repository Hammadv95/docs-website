import re

p="main.py"
s=open(p,"r",encoding="utf8").read()

# Replace the whole sb_storage_upload function with a known-good version
pat = re.compile(r"async def sb_storage_upload\(.*?\n\)", re.S)

# Find function block start/end via simple markers
start = s.find("async def sb_storage_upload")
if start == -1:
    raise SystemExit("sb_storage_upload not found")

# naive: cut from start to next 'async def ' after it
rest = s[start:]
m = re.search(r"\nasync def ", rest[1:])
end = start + (m.start() + 1) if m else len(s)

new_func = """async def sb_storage_upload(bucket: str, path: str, content: bytes, content_type: str) -> None:
    # Use PUT upload. This is the most reliable for Supabase Storage object uploads.
    url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{path}"
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.put(url, headers=headers, content=content)
        if r.status_code >= 400:
            raise HTTPException(status_code=500, detail=f"Supabase Storage upload error {r.status_code}: {r.text}")
"""

s2 = s[:start] + new_func + s[end:]
open(p,"w",encoding="utf8").write(s2)
print(" Replaced sb_storage_upload with PUT + readable errors")
