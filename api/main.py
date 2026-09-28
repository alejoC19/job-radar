from __future__ import annotations

import io
import os

import requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from job_radar.config import ProfileConfig, ScoringConfig, load_config
from job_radar.export import build_workbook
from job_radar.scoring import score_listing
from job_radar.sources.bumeran import BumeranScraper
from job_radar.sources.computrabajo import ComputrabajoScraper

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
FRONTEND_ORIGINS = [o.strip() for o in os.environ.get("FRONTEND_ORIGINS", "").split(",") if o.strip()]

app = FastAPI(title="job-radar API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _fetch_user_profiles(access_token: str) -> list[ProfileConfig]:
    """Trae los cv_profiles del usuario dueño del token, dejando que RLS en
    Supabase haga el filtrado (se reenvía su propio access token, no se usa
    una service key)."""
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/cv_profiles",
        params={"select": "id,name,keywords", "order": "created_at.asc"},
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {access_token}",
        },
        timeout=15,
    )
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Token invalido o expirado")
    response.raise_for_status()
    return [
        ProfileConfig(key=row["id"], name=row["name"], keywords=row.get("keywords") or {})
        for row in response.json()
    ]


@app.post("/generate")
def generate(authorization: str | None = Header(default=None)) -> StreamingResponse:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Falta el header Authorization")
    access_token = authorization.split(" ", 1)[1]

    profiles = _fetch_user_profiles(access_token)
    if not profiles:
        raise HTTPException(status_code=400, detail="Todavia no tenes perfiles de CV cargados")

    defaults = load_config()
    scoring_config = ScoringConfig(profiles=profiles, bonus=defaults.bonus, penalties=defaults.penalties)

    listings = []
    for scraper in (ComputrabajoScraper(), BumeranScraper()):
        listings.extend(scraper.fetch())

    scored = [(listing, score_listing(listing, scoring_config)) for listing in listings]
    scored.sort(key=lambda pair: max((r.score for r in pair[1]), default=0), reverse=True)

    workbook = build_workbook(scored, scoring_config.profiles)
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=avisos_job_radar.xlsx"},
    )
