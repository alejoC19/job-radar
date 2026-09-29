from __future__ import annotations

import io
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from docx import Document as DocxDocument
from fastapi import FastAPI, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import BaseModel, Field
from pypdf import PdfReader

from job_radar.config import ProfileConfig, ScoringConfig, load_config
from job_radar.export import build_workbook
from job_radar.models import JobListing
from job_radar.scoring import score_listing

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
FRONTEND_ORIGINS = [o.strip() for o in os.environ.get("FRONTEND_ORIGINS", "").split(",") if o.strip()]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.1-flash-lite"
MATCH_WINDOW_DAYS = 15

app = FastAPI(title="job-radar API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gemini tiene tier gratuito de verdad (sin tarjeta, con cuota diaria
# generosa via Google AI Studio) - se usa solo para /profiles/from-cv, un
# llamado por CV subido. Construido con una key placeholder cuando falta la
# variable de entorno para que el resto de la app (que no la necesita) no se
# caiga al importar el modulo; el endpoint valida GEMINI_API_KEY antes de usarlo.
gemini_client = genai.Client(api_key=GEMINI_API_KEY or "not-configured")


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
    name: str
    keywords: dict[str, float]


class _KeywordWeight(BaseModel):
    keyword: str = Field(description="Keyword en minusculas y sin acentos")
    weight: float = Field(description="Peso de 1 a 3 (3 = mas determinante del perfil)")


class _GeminiCvSchema(BaseModel):
    """Schema que se le pide a Gemini. Las keywords van en lista, no en dict:
    el modo gratuito de la API (Gemini Developer API) no soporta objetos con
    additionalProperties (diccionarios de forma libre) en salida estructurada,
    solo en modo Enterprise/Vertex. Se convierte a dict despues, para no
    cambiar el contrato del endpoint."""

    name: str = Field(description="Nombre corto para el perfil, ej: 'QA Automation' o 'Desarrollador Backend'")
    keywords: list[_KeywordWeight] = Field(
        description="Keywords relevantes para matchear avisos de trabajo en Argentina contra este CV"
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


_CV_SYSTEM_PROMPT = (
    "Sos un asistente que arma perfiles de busqueda de empleo a partir de un CV. "
    "Priorizá tecnologias, skills, rol y seniority reales del CV: no inventes "
    "nada que no este en el texto. Las keywords van en minusculas y sin acentos."
)


# Códigos transitorios del tier gratuito de Gemini (sobrecarga momentánea o
# rate limit): vale la pena reintentar en vez de devolver el error al toque.
_GEMINI_RETRYABLE_CODES = {429, 503}
_GEMINI_MAX_ATTEMPTS = 3
_GEMINI_RETRY_BACKOFF_SECONDS = 2


def _extract_cv_profile(text: str) -> CvProfileExtraction:
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY no esta configurada en el backend")

    for attempt in range(_GEMINI_MAX_ATTEMPTS):
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=text[:20000],
                config=genai_types.GenerateContentConfig(
                    system_instruction=_CV_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=_GeminiCvSchema,
                ),
            )
            break
        except genai_errors.APIError as exc:
            is_last_attempt = attempt == _GEMINI_MAX_ATTEMPTS - 1
            if exc.code not in _GEMINI_RETRYABLE_CODES or is_last_attempt:
                raise HTTPException(status_code=502, detail=f"Error llamando a la IA: {exc}") from exc
            time.sleep(_GEMINI_RETRY_BACKOFF_SECONDS * (attempt + 1))

    parsed = response.parsed
    if not isinstance(parsed, _GeminiCvSchema):
        raise HTTPException(status_code=502, detail="La IA no pudo armar un perfil valido, proba de nuevo")

    keywords = {item.keyword: item.weight for item in parsed.keywords}
    return CvProfileExtraction(name=parsed.name, keywords=keywords)


@app.post("/profiles/from-cv")
async def profile_from_cv(file: UploadFile, authorization: str | None = Header(default=None)) -> dict:
    access_token = _bearer_token(authorization)
    _require_valid_session(access_token)

    content = await file.read()
    text = _extract_cv_text(file.filename or "", content).strip()
    if len(text) < 50:
        raise HTTPException(status_code=400, detail="No se pudo leer texto del CV")

    extracted = _extract_cv_profile(text)
    return {"name": extracted.name, "keywords": extracted.keywords}
