import re

p = "main.py"
s = open(p, "r", encoding="utf8").read()

# ensure uuid import exists
if "import uuid" not in s:
    s = s.replace("import os, time, hashlib", "import os, time, hashlib\nimport uuid")

# Replace the specific TEMP insert block in admin_upload (best-effort)
# We'll do a regex-based replacement for the "else:" branch that inserts TEMP.
pattern = re.compile(
    r"else:\s*\n\s*created\s*=\s*await sb_insert\(\"documents\",\s*\{.*?\"storage_path\":\s*\"TEMP\".*?\}\)\s*\n\s*doc_id\s*=\s*created\[\"id\"\]\s*\n\s*storage_path\s*=\s*f\"{doc_id}\.pdf\"\s*\n\s*await sb_storage_upload\(\"docs\",\s*storage_path,\s*pdf_bytes,\s*\"application/pdf\"\)\s*\n\s*doc_row\s*=\s*await sb_update_by_id\(\"documents\",\s*doc_id,\s*\{\"storage_path\":\s*storage_path\}\)\s*",
    re.S
)

replacement = """else:
        doc_id = str(uuid.uuid4())
        storage_path = f"{doc_id}.pdf"

        # Upload first so storage_path is never TEMP
        await sb_storage_upload("docs", storage_path, pdf_bytes, "application/pdf")

        doc_row = await sb_insert("documents", {
            "id": doc_id,
            "slug": computed_slug,
            "title": title,
            "summary": summary,
            "is_published": True,
            "storage_path": storage_path,
            "sha256": digest,
            "file_size": len(pdf_bytes),
            "extracted_text": extracted,
            "updated_at": now_iso,
        })
"""

new_s, n = pattern.subn(replacement, s, count=1)
if n == 0:
    print("⚠️ Could not find the TEMP insert block to replace. No changes made (except maybe uuid import).")
    open(p, "w", encoding="utf8").write(s)
else:
    open(p, "w", encoding="utf8").write(new_s)
    print("✅ Patched upload flow to avoid TEMP (replaced block:", n, ")")
