from __future__ import annotations

import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from ..models import JobListing
from ..salary import extract_salary
from .base import SEARCH_TERMS, Scraper, slugify

BASE_URL = "https://ar.computrabajo.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
MAX_PAGES = 2
REQUEST_DELAY_SECONDS = 1.0
TIMEOUT_SECONDS = 20


class ComputrabajoScraper(Scraper):
    """Scraper de Computrabajo Argentina.

    No hay RSS ni API publica: se parsea el HTML de busqueda
    (ar.computrabajo.com/trabajo-de-{keyword}, paginado con ?p=N).
    """

    name = "computrabajo"

    def __init__(self, search_terms: list[str] | None = None, max_pages: int = MAX_PAGES):
        self.search_terms = SEARCH_TERMS if search_terms is None else search_terms
        self.max_pages = max_pages

    def fetch(self) -> list[JobListing]:
        listings: dict[str, JobListing] = {}
        for term in self.search_terms:
            for page in range(1, self.max_pages + 1):
                html = self._fetch_page(term, page)
                if html is None:
                    break
                page_listings = self._parse(html)
                if not page_listings:
                    break
                for listing in page_listings:
                    listings.setdefault(listing.url, listing)
                time.sleep(REQUEST_DELAY_SECONDS)
        return list(listings.values())

    def _fetch_page(self, term: str, page: int) -> str | None:
        url = f"{BASE_URL}/trabajo-de-{slugify(term)}"
        if page > 1:
            url = f"{url}?p={page}"
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"[computrabajo] error buscando '{term}' pagina {page}: {exc}")
            return None
        return response.text

    def _parse(self, html: str) -> list[JobListing]:
        soup = BeautifulSoup(html, "html.parser")
        listings = []
        for article in soup.select("article.box_offer"):
            listing = self._parse_article(article)
            if listing is not None:
                listings.append(listing)
        return listings

    def _parse_article(self, article: Tag) -> JobListing | None:
        link = article.select_one("h2 a.js-o-link")
        if link is None or not link.get("href"):
            return None
        title = link.get_text(strip=True)
        url = urljoin(BASE_URL, link["href"].split("#")[0])

        extra_text = self._extract_extra(article)

        return JobListing(
            title=title,
            company=self._extract_company(article),
            url=url,
            description=extra_text,
            location=self._extract_location(article),
            salary_text=extract_salary(f"{title} {extra_text}"),
            source=self.name,
        )

    @staticmethod
    def _extract_company(article: Tag) -> str:
        company_p = article.select_one("p.dFlex.vm_fx")
        if company_p is None:
            return ""
        link = company_p.select_one("a[offer-grid-article-company-url]")
        if link is not None:
            return link.get_text(strip=True)
        for tag in company_p.select("span.fx_none, span.icon"):
            tag.decompose()
        return company_p.get_text(strip=True)

    @staticmethod
    def _extract_location(article: Tag) -> str:
        for p in article.select("p.fs16.fc_base.mt5"):
            if "dFlex" in (p.get("class") or []):
                continue
            return p.get_text(strip=True)
        return ""

    @staticmethod
    def _extract_extra(article: Tag) -> str:
        info = article.select_one("div.fs13.mt15")
        return info.get_text(" ", strip=True) if info is not None else ""
