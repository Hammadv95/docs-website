import re

p = "main.py"
s = open(p, "r", encoding="utf8").read()

# Patch sb_storage_download to use authenticated endpoint + readable error
pattern = re.compile(r"async def sb_storage_download\(bucket: str, path: str\).*?return r\.content", re.S)

replacement = """async def sb_storage_download(bucket: str, path: str) -> bytes:
    # Private buckets require the authenticated download endpoint
    url = f"{SUPABASE_URL}/storage/v1/object/authenticated/{bucket}/{path}"
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.get(url, headers=headers)
        if r.status_code >= 400:
            raise HTTPException(status_code=500, detail=f"Supabase Storage download error {r.status_code}: {r.text}")
        return r.content
"""

new_s, n = pattern.subn(replacement, s, count=1)
open(p, "w", encoding="utf8").write(new_s)
print("✅ patched sb_storage_download (replaced:", n, ")")
