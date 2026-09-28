from __future__ import annotations

from ..models import JobListing
from .base import Scraper


class BumeranScraper(Scraper):
    """TODO: implementar.

    Bloqueado por falta de acceso de red a bumeran.com.ar desde el entorno
    de desarrollo (ver README, seccion "Estado actual"). Antes de escribir
    un scraper con Playwright, revisar si el sitio expone RSS o un JSON
    interno que se pueda consumir directo.
    """

    name = "bumeran"

    def fetch(self) -> list[JobListing]:
        raise NotImplementedError("Pendiente: ver TODO en este archivo")
