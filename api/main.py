from __future__ import annotations

import io
import os
from datetime import datetime, timedelta, timezone

import requests
from anthropic import Anthropic
from docx import Document as DocxDocument
from fastapi import FastAPI, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pypdf import PdfReader

from job_radar.config import ProfileConfig, ScoringConfig, load_config
from job_radar.export import build_workbook
from job_radar.models import JobListing
from job_radar.scoring import score_listing

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
FRONTEND_ORIGINS = [o.strip() for o in os.environ.get("FRONTEND_ORIGINS", "").split(",") if o.strip()]
MATCH_WINDOW_DAYS = 15

app = FastAPI(title="job-radar API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

anthropic_client = Anthropic()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _require_valid_session(access_token: str) -> None:
    response = requests.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Token invalido o expirado")


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Falta el header Authorization")
    return authorization.split(" ", 1)[1]


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


def _fetch_recent_listings(access_token: str, since_days: int = MATCH_WINDOW_DAYS) -> list[JobListing]:
    """Trae los avisos guardados por el cron en los ultimos `since_days` dias
    (tabla job_listings, poblada por job_radar.ingest). Igual que con los
    perfiles, RLS filtra: solo usuarios logueados pueden leer."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/job_listings",
        params={
            "select": "title,company,location,description,salary_text,url,source",
            "scraped_at": f"gte.{cutoff}",
            "order": "scraped_at.desc",
            "limit": "5000",
        },
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {access_token}",
        },
        timeout=30,
    )
    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Token invalido o expirado")
    response.raise_for_status()
    return [JobListing(**row) for row in response.json()]


@app.post("/generate")
def generate(authorization: str | None = Header(default=None)) -> StreamingResponse:
    access_token = _bearer_token(authorization)

    profiles = _fetch_user_profiles(access_token)
    if not profiles:
        raise HTTPException(status_code=400, detail="Todavia no tenes perfiles de CV cargados")

    defaults = load_config()
    scoring_config = ScoringConfig(profiles=profiles, bonus=defaults.bonus, penalties=defaults.penalties)

    listings = _fetch_recent_listings(access_token)

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


class CvProfileExtraction(BaseModel):
    name: str = Field(description="Nombre corto para el perfil, ej: 'QA Automation' o 'Desarrollador Backend'")
    keywords: dict[str, float] = Field(
        description=(
            "Keywords relevantes para matchear avisos de trabajo en Argentina contra este CV, "
            "en minusculas y sin acentos, con un peso de 1 a 3 (3 = mas determinante del perfil)"
        )
    )


def _extract_cv_text(filename: str, content: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if lower.endswith(".docx"):
        document = DocxDocument(io.BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    raise HTTPException(status_code=400, detail="Solo se aceptan archivos .pdf o .docx")


@app.post("/profiles/from-cv")
async def profile_from_cv(file: UploadFile, authorization: str | None = Header(default=None)) -> dict:
    access_token = _bearer_token(authorization)
    _require_valid_session(access_token)

    content = await file.read()
    text = _extract_cv_text(file.filename or "", content).strip()
    if len(text) < 50:
        raise HTTPException(status_code=400, detail="No se pudo leer texto del CV")

    response = anthropic_client.messages.parse(
        model="claude-opus-5-5",
        max_tokens=2000,
        system=(
            "Sos un asistente que arma perfiles de busqueda de empleo a partir de un CV. "
            "Te paso el texto de un CV y tenes que devolver un nombre corto para el perfil "
            "y un diccionario de keywords relevantes para matchear avisos de trabajo en "
            "Argentina, con un peso de 1 a 3 (3 = mas determinante). Priorizá tecnologias, "
            "skills, rol y seniority reales del CV (no inventes nada que no este), en "
            "minusculas y sin acentos."
        ),
        messages=[{"role": "user", "content": text[:20000]}],
        output_format=CvProfileExtraction,
    )
    extracted = response.parsed_output
    return {"name": extracted.name, "keywords": extracted.keywords}
