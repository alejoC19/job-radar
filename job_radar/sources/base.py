from __future__ import annotations

import re
import unicodedata
from abc import ABC, abstractmethod

from ..models import JobListing

# Terminos de busqueda que cubren los 3 perfiles (config.yaml). Son deliberadamente
# generales: el scoring despues filtra que tan relevante es cada aviso para cada
# perfil, esto solo define que tan amplia es la red que tiran los scrapers.
SEARCH_TERMS: list[str] = [
    "qa automation",
    "tester",
    "desarrollador",
    "analista contable",
]


class Scraper(ABC):
    """Interfaz comun para las fuentes de avisos. Cada sitio implementa fetch()."""

    name: str = "base"

    @abstractmethod
    def fetch(self) -> list[JobListing]:
        raise NotImplementedError


def slugify(text: str) -> str:
    """Normaliza texto libre a un slug de URL: minusculas, sin acentos, con guiones."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower())
    return text.strip("-")
