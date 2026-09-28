from __future__ import annotations

import time
from html import unescape

import requests

from ..models import JobListing
from ..salary import extract_salary
from .base import SEARCH_TERMS, Scraper, slugify

SEARCH_URL = "https://www.bumeran.com.ar/api/avisos/searchV2"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
PAGE_SIZE = 20
MAX_PAGES = 2
REQUEST_DELAY_SECONDS = 1.0
TIMEOUT_SECONDS = 20


class BumeranScraper(Scraper):
    """Scraper de Bumeran Argentina.

    El sitio renderiza los resultados con React del lado del cliente (no hay
    HTML util para parsear), pero el frontend llama a una API JSON interna
    (POST /api/avisos/searchV2, con header x-site-id: BMAR) que se puede
    consumir directo con requests, sin necesidad de un navegador.
    """

    name = "bumeran"

    def __init__(self, search_terms: list[str] | None = None, max_pages: int = MAX_PAGES):
        self.search_terms = SEARCH_TERMS if search_terms is None else search_terms
        self.max_pages = max_pages

    def fetch(self) -> list[JobListing]:
        listings: dict[str, JobListing] = {}
        for term in self.search_terms:
            for page in range(self.max_pages):
                items = self._fetch_page(term, page)
                if not items:
                    break
                for item in items:
                    listing = self._parse_item(item)
                    if listing is not None:
                        listings.setdefault(listing.url, listing)
                time.sleep(REQUEST_DELAY_SECONDS)
        return list(listings.values())

    def _fetch_page(self, term: str, page: int) -> list[dict]:
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": f"https://www.bumeran.com.ar/empleos-busqueda-{slugify(term)}.html",
            "x-site-id": "BMAR",
        }
        params = {"pageSize": PAGE_SIZE, "page": page, "sort": "RELEVANTES"}
        body = {"filtros": [], "query": term}
        try:
            response = requests.post(SEARCH_URL, params=params, json=body, headers=headers, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"[bumeran] error buscando '{term}' pagina {page}: {exc}")
            return []
        return data.get("content", [])

    @staticmethod
    def _parse_item(item: dict) -> JobListing | None:
        job_id = item.get("id")
        title = unescape((item.get("titulo") or "").strip())
        if not job_id or not title:
            return None

        description = unescape((item.get("detalle") or "").strip())
        modality = item.get("modalidadTrabajo") or ""
        if modality:
            description = f"{description} {modality}".strip()

        return JobListing(
            title=title,
            company=unescape((item.get("empresa") or "").strip()) or "Confidencial",
            url=f"https://www.bumeran.com.ar/empleos/{slugify(title)}-{job_id}.html",
            description=description,
            location=unescape((item.get("localizacion") or "").strip()),
            salary_text=extract_salary(f"{title} {description}"),
            source="bumeran",
        )
