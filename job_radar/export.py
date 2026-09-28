from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from .config import ProfileConfig
from .models import JobListing, ScoreResult

HEADERS = ["Titulo", "Empresa", "Puntaje", "Sueldo", "Ubicacion", "Link", "Fuente"]


def build_workbook(
    scored_listings: list[tuple[JobListing, list[ScoreResult]]],
    profiles: list[ProfileConfig],
) -> Workbook:
    """Arma un Excel con una hoja por perfil, cada uno con los avisos donde
    ese perfil es el CV sugerido (mayor puntaje), ordenados de mayor a menor.
    """
    wb = Workbook()
    wb.remove(wb.active)

    for profile in profiles:
        rows: list[tuple[JobListing, ScoreResult]] = []
        for listing, results in scored_listings:
            best = max(results, key=lambda r: r.score)
            if best.profile_key == profile.key:
                rows.append((listing, best))
        rows.sort(key=lambda pair: pair[1].score, reverse=True)

        ws = wb.create_sheet(title=profile.name[:31])
        ws.append(HEADERS)
        for listing, result in rows:
            ws.append(
                [
                    listing.title,
                    listing.company,
                    result.score,
                    listing.salary_text or "",
                    listing.location,
                    listing.url,
                    listing.source,
                ]
            )

    return wb


def save_workbook(workbook: Workbook, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
