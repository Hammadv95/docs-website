import os, time, hashlib
import uuid
from typing import Optional, Dict, List

import fitz  # PyMuPDF
import httpx
import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext
from slugify import slugify

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

MEILI_URL = os.environ.get("MEILI_URL", "http://localhost:7700").rstrip("/")
MEILI_MASTER_KEY = os.environ.get("MEILI_MASTER_KEY", "change-me")
MEILI_INDEX = os.environ.get("MEILI_INDEX", "documents")

JWT_SECRET = os.environ.get("ADMIN_JWT_SECRET", "dev-secret-change-me")
JWT_EXPIRES_MIN = int(os.environ.get("ADMIN_JWT_EXPIRES_MIN", "720"))

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="Docs Website API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Supabase REST helpers ----------------
def sb_headers() -> Dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

async def sb_select_one(table: str, query: str) -> Optional[dict]:
    url = f"{SUPABASE_URL}/rest/v1/{table}{query}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=sb_headers())
        if r.status_code >= 400:
            raise HTTPException(status_code=500, detail=f"Supabase Storage error {r.status_code}: {r.text}")
        data = r.json()
        return data[0] if data else None

async def sb_list(table: str, query: str) -> List[dict]:
    url = f"{SUPABASE_URL}/rest/v1/{table}{query}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=sb_headers())
        r.raise_for_status()
        return r.json()

async def sb_insert(table: str, payload: dict) -> dict:
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, headers={**sb_headers(), "Prefer": "return=representation"}, json=payload)
        r.raise_for_status()
        return r.json()[0]

async def sb_update_by_id(table: str, row_id: str, payload: dict) -> dict:
    url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{row_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.patch(url, headers={**sb_headers(), "Prefer": "return=representation"}, json=payload)
        r.raise_for_status()
        return r.json()[0]

# ---------------- Supabase Storage helpers ----------------
async def sb_storage_upload(bucket: str, path: str, content: bytes, content_type: str) -> None:
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

async def sb_storage_download(bucket: str, path: str) -> bytes:
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


# ---------------- Meilisearch helpers ----------------
async def meili_setup() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{MEILI_URL}/indexes/{MEILI_INDEX}", headers={"Authorization": f"Bearer {MEILI_MASTER_KEY}"})
        if r.status_code == 404:
            cr = await client.post(
                f"{MEILI_URL}/indexes",
                headers={"Authorization": f"Bearer {MEILI_MASTER_KEY}"},
                json={"uid": MEILI_INDEX, "primaryKey": "id"},
            )
            cr.raise_for_status()

        await client.put(
            f"{MEILI_URL}/indexes/{MEILI_INDEX}/settings",
            headers={"Authorization": f"Bearer {MEILI_MASTER_KEY}"},
            json={
                "searchableAttributes": ["title", "summary", "content"],
                "filterableAttributes": ["is_published"],
                "sortableAttributes": ["updated_at"],
            },
        )

@app.on_event("startup")
async def _startup():
    await meili_setup()

async def meili_upsert(doc: dict) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{MEILI_URL}/indexes/{MEILI_INDEX}/documents",
            headers={"Authorization": f"Bearer {MEILI_MASTER_KEY}"},
            json=[doc],
        )
        r.raise_for_status()

async def meili_search(q: str, limit: int = 20) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{MEILI_URL}/indexes/{MEILI_INDEX}/search",
            headers={"Authorization": f"Bearer {MEILI_MASTER_KEY}"},
            json={"q": q, "limit": limit, "filter": "is_published = true"},
        )
        r.raise_for_status()
        return r.json()

# ---------------- Auth helpers ----------------
def make_admin_token(email: str) -> str:
    now = int(time.time())
    payload = {"sub": email, "iat": now, "exp": now + JWT_EXPIRES_MIN * 60, "role": "admin"}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def require_admin(auth_header: Optional[str]) -> str:
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing admin token")
    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Not admin")
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

# ---------------- PDF helpers ----------------
def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def extract_pdf_text(pdf_bytes: bytes, max_chars: int = 2_000_000) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    parts, total = [], 0
    for page in doc:
        txt = page.get_text("text") or ""
        if not txt:
            continue
        remaining = max_chars - total
        if remaining <= 0:
            break
        parts.append(txt[:remaining])
        total += len(parts[-1])
    return "\n".join(parts).strip()

# ---------------- Routes ----------------
@app.get("/")
async def root():
    return {"status": "Backend Running"}

@app.get("/test-supabase")
async def test_supabase():
    url = f"{SUPABASE_URL}/rest/v1/documents?select=*"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=sb_headers())
        return {"status_code": r.status_code, "response": r.json() if r.status_code == 200 else r.text}

@app.get("/api/search")
async def search(q: str, limit: int = 20):
    q = (q or "").strip()
    if not q:
        return {"query": q, "hits": [], "estimatedTotalHits": 0}
    res = await meili_search(q, limit=limit)
    hits = [{"slug": h["slug"], "title": h["title"], "summary": h.get("summary",""), "updated_at": h.get("updated_at")} for h in res.get("hits", [])]
    return {"query": q, "hits": hits, "estimatedTotalHits": res.get("estimatedTotalHits", 0)}

@app.get("/api/docs")
async def list_docs():
    rows = await sb_list("documents", "?select=slug,title,summary,updated_at&is_published=eq.true&order=updated_at.desc")
    return {"docs": rows}

@app.get("/api/docs/{slug}")
async def get_doc(slug: str):
    row = await sb_select_one("documents", f"?select=slug,title,summary,updated_at,is_published&slug=eq.{slug}&limit=1")
    if not row or not row.get("is_published"):
        raise HTTPException(status_code=404, detail="Not found")
    row["view_url"] = f"/api/docs/{slug}/view"
    return row

@app.get("/api/docs/{slug}/view")
async def view_pdf(slug: str):
    row = await sb_select_one("documents", f"?select=storage_path,title,is_published&slug=eq.{slug}&limit=1")
    if not row or not row.get("is_published"):
        raise HTTPException(status_code=404, detail="Not found")
    pdf_bytes = await sb_storage_download("docs", row["storage_path"])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{row["title"]}.pdf"', "Cache-Control": "private, max-age=0, no-store"},
    )

@app.post("/admin/login")
async def admin_login(email: str = Form(...), password: str = Form(...)):
    user = await sb_select_one("admin_users", f"?select=email,password_hash&email=eq.{email}&limit=1")
    if not user or not pwd_ctx.verify(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": make_admin_token(email)}

@app.post("/admin/upload")
async def admin_upload(
    authorization: Optional[str] = Header(None),
    title: str = Form(...),
    slug: Optional[str] = Form(None),
    summary: str = Form(""),
    pdf: UploadFile = File(...),
):
    require_admin(authorization)

    if pdf.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(status_code=400, detail="Only PDF uploads allowed")

    pdf_bytes = await pdf.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        _ = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid PDF")

    computed_slug = slugify(slug or title)
    if not computed_slug:
        raise HTTPException(status_code=400, detail="Invalid slug/title")

    digest = sha256_bytes(pdf_bytes)
    extracted = extract_pdf_text(pdf_bytes)
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    existing = await sb_select_one("documents", f"?select=id,slug&slug=eq.{computed_slug}&limit=1")
    if existing:
        doc_id = existing["id"]
        storage_path = f"{doc_id}.pdf"
        await sb_storage_upload("docs", storage_path, pdf_bytes, "application/pdf")
        doc_row = await sb_update_by_id("documents", doc_id, {
            "title": title,
            "summary": summary,
            "storage_path": storage_path,
            "sha256": digest,
            "file_size": len(pdf_bytes),
            "extracted_text": extracted,
            "updated_at": now_iso,
            "is_published": True,
            "slug": computed_slug,
        })
    else:
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
    await meili_upsert({
            "id": doc_row["id"],
            "slug": doc_row["slug"],
            "title": doc_row["title"],
            "summary": doc_row.get("summary", ""),
            "updated_at": doc_row.get("updated_at"),
            "is_published": bool(doc_row.get("is_published", True)),
            "content": doc_row.get("extracted_text", ""),
        })

    return {"ok": True, "slug": doc_row["slug"], "url": f"/docs/{doc_row['slug']}"}

# ---------------- Admin: Reindex all docs into Meilisearch ----------------
@app.post("/admin/reindex")
async def admin_reindex(authorization: Optional[str] = Header(None)):
    require_admin(authorization)

    rows = await sb_list(
        "documents",
        "?select=id,slug,title,summary,updated_at,is_published,extracted_text&order=updated_at.desc"
    )

    batch = []
    pushed = 0

    async with httpx.AsyncClient(timeout=60) as client:
        for r in rows:
            batch.append({
                "id": r["id"],
                "slug": r["slug"],
                "title": r["title"],
                "summary": r.get("summary", "") or "",
                "updated_at": r.get("updated_at"),
                "is_published": bool(r.get("is_published", True)),
                "content": (r.get("extracted_text") or ""),
            })

            if len(batch) >= 100:
                resp = await client.post(
                    f"{MEILI_URL}/indexes/{MEILI_INDEX}/documents",
                    headers={"Authorization": f"Bearer {MEILI_MASTER_KEY}"},
                    json=batch,
                )
                resp.raise_for_status()
                pushed += len(batch)
                batch = []

        if batch:
            resp = await client.post(
                f"{MEILI_URL}/indexes/{MEILI_INDEX}/documents",
                headers={"Authorization": f"Bearer {MEILI_MASTER_KEY}"},
                json=batch,
            )
            resp.raise_for_status()
            pushed += len(batch)

    return {"ok": True, "pushed": pushed}



@app.get("/admin/env-check")
def env_check():
    # Returns True/False for presence (does NOT leak secrets)
    return {var: bool(os.getenv(var)) for var in REQUIRED_ENV_VARS}


