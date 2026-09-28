from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import JobListing


class Scraper(ABC):
    """Interfaz comun para las fuentes de avisos. Cada sitio implementa fetch()."""

    name: str = "base"

    @abstractmethod
    def fetch(self) -> list[JobListing]:
        raise NotImplementedError
