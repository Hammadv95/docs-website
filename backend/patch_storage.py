import io

p = "main.py"
s = open(p, "r", encoding="utf8").read()

s = s.replace("r = await client.post(url, headers=headers, content=content)",
              "r = await client.put(url, headers=headers, content=content)")

# Replace the first occurrence of r.raise_for_status() with our readable error
needle = "r.raise_for_status()"
if needle in s:
    s = s.replace(needle,
                  'if r.status_code >= 400:\n            raise HTTPException(status_code=500, detail=f"Supabase Storage error {r.status_code}: {r.text}")',
                  1)

open(p, "w", encoding="utf8").write(s)
print("patched main.py")
