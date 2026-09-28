from __future__ import annotations

from html import escape

import requests

from .models import JobListing, ScoreResult

TELEGRAM_API = "https://api.telegram.org/bot{token}"
TELEGRAM_MESSAGE_LIMIT = 4096
HEADER_RESERVE = 120  # margen para el encabezado (que incluye el numero de pagina)


def _format_entry(index: int, listing: JobListing, result: ScoreResult) -> str:
    salary = f" | {escape(listing.salary_text)}" if listing.salary_text else ""
    return (
        f"{index}. <b>{escape(listing.title)}</b> - {escape(listing.company)}\n"
        f"   Puntaje: {result.score:.0f} | CV sugerido: {escape(result.profile_name)}{salary}\n"
        f"   {listing.url}"
    )


def format_messages(ranked: list[tuple[JobListing, ScoreResult]]) -> list[str]:
    """Arma uno o mas mensajes con TODOS los avisos nuevos (no solo un top fijo),
    partiendo en varios mensajes si no entran en el limite de Telegram (4096
    caracteres por mensaje).
    """
    if not ranked:
        return ["<b>Job Radar - Avisos nuevos de hoy</b>\n\nNo hay avisos nuevos hoy."]

    entries = [_format_entry(i, listing, result) for i, (listing, result) in enumerate(ranked, start=1)]

    pages: list[list[str]] = [[]]
    page_length = 0
    for entry in entries:
        entry_length = len(entry) + 2
        if pages[-1] and page_length + entry_length > TELEGRAM_MESSAGE_LIMIT - HEADER_RESERVE:
            pages.append([])
            page_length = 0
        pages[-1].append(entry)
        page_length += entry_length

    total_pages = len(pages)
    messages = []
    for page_num, page_entries in enumerate(pages, start=1):
        header = f"<b>Job Radar - Avisos nuevos de hoy</b> ({len(ranked)} en total)"
        if total_pages > 1:
            header += f" - parte {page_num}/{total_pages}"
        messages.append("\n".join([header, "", *page_entries]))
    return messages


def send_message(token: str, chat_id: str, text: str) -> None:
    url = f"{TELEGRAM_API.format(token=token)}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    response.raise_for_status()


def send_document(token: str, chat_id: str, file_path: str, caption: str | None = None) -> None:
    url = f"{TELEGRAM_API.format(token=token)}/sendDocument"
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption
    with open(file_path, "rb") as f:
        response = requests.post(url, data=data, files={"document": f}, timeout=60)
    response.raise_for_status()
