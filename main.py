import os
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

app = FastAPI(title="Docs Website API")


def sb_headers():
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }


@app.get("/")
async def root():
    return {"status": "Backend Running"}


@app.get("/test-supabase")
async def test_supabase():
    url = f"{SUPABASE_URL}/rest/v1/documents?select=*"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=sb_headers())
        return {
            "status_code": r.status_code,
            "response": r.json() if r.status_code == 200 else r.text
        }
