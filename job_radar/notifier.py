from __future__ import annotations

from html import escape

import requests

from .models import JobListing, ScoreResult

TELEGRAM_API = "https://api.telegram.org/bot{token}"


def format_top10_message(ranked: list[tuple[JobListing, ScoreResult]]) -> str:
    lines = ["<b>Job Radar - Avisos nuevos de hoy</b>", ""]
    for i, (listing, result) in enumerate(ranked[:10], start=1):
        salary = f" | {escape(listing.salary_text)}" if listing.salary_text else ""
        lines.append(
            f"{i}. <b>{escape(listing.title)}</b> - {escape(listing.company)}\n"
            f"   Puntaje: {result.score:.0f} | CV sugerido: {escape(result.profile_name)}{salary}\n"
            f"   {listing.url}"
        )
    return "\n".join(lines)


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
