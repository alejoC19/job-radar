from __future__ import annotations

import os
from pathlib import Path

from .config import load_config
from .dedup import SeenStore
from .export import build_workbook, save_workbook
from .ingest import cleanup_old_listings, push_listings
from .models import JobListing
from .notifier import format_messages, send_document, send_message
from .scoring import score_listing
from .sources.base import Scraper

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEEN_PATH = DATA_DIR / "seen.json"
EXPORT_PATH = DATA_DIR / "avisos_del_dia.xlsx"


def _ingest_into_supabase(listings: list[JobListing]) -> None:
    """Best-effort: si Supabase no esta configurado o falla, no corta la
    corrida (el mensaje de Telegram no depende de esto)."""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY")
    if not supabase_url or not supabase_anon_key:
        return
    try:
        push_listings(supabase_url, supabase_anon_key, listings)
        cleanup_old_listings(supabase_url, supabase_anon_key)
    except Exception as exc:  # noqa: BLE001 - nunca debe tumbar la corrida
        print(f"No se pudieron guardar los avisos en Supabase: {exc}")


def run(sources: list[Scraper]) -> None:
    scoring_config = load_config()
    seen = SeenStore(SEEN_PATH)

    all_listings: list[JobListing] = []
    for source in sources:
        all_listings.extend(source.fetch())

    _ingest_into_supabase(all_listings)

    new_listings = [listing for listing in all_listings if not seen.is_seen(listing.url)]

    if not new_listings:
        print("No hay avisos nuevos hoy.")
        return

    scored = [(listing, score_listing(listing, scoring_config)) for listing in new_listings]
    scored.sort(key=lambda pair: max(r.score for r in pair[1]), reverse=True)

    workbook = build_workbook(scored, scoring_config.profiles)
    save_workbook(workbook, EXPORT_PATH)

    top_ranked = [(listing, max(results, key=lambda r: r.score)) for listing, results in scored]
    messages = format_messages(top_ranked)

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    for message in messages:
        send_message(token, chat_id, message)
    send_document(token, chat_id, str(EXPORT_PATH), caption="Avisos nuevos de hoy, por perfil")

    for listing in new_listings:
        seen.mark_seen(listing.url)
    seen.save()


if __name__ == "__main__":
    from .sources.bumeran import BumeranScraper
    from .sources.computrabajo import ComputrabajoScraper

    run([ComputrabajoScraper(), BumeranScraper()])
