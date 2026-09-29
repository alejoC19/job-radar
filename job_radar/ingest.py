from __future__ import annotations

import requests

from .models import JobListing


def push_listings(supabase_url: str, supabase_anon_key: str, listings: list[JobListing]) -> int:
    """Sube los avisos scrapeados a la tabla job_listings via la RPC
    ingest_job_listings (upsert por URL). No falla si Supabase esta caido:
    quien llama decide que hacer con la excepcion.
    """
    if not listings:
        return 0

    payload = [
        {
            "source": listing.source,
            "url": listing.url,
            "title": listing.title,
            "company": listing.company,
            "location": listing.location,
            "description": listing.description,
            "salary_text": listing.salary_text,
        }
        for listing in listings
    ]
    response = requests.post(
        f"{supabase_url}/rest/v1/rpc/ingest_job_listings",
        headers={
            "apikey": supabase_anon_key,
            "Authorization": f"Bearer {supabase_anon_key}",
            "Content-Type": "application/json",
        },
        json={"payload": payload},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def cleanup_old_listings(supabase_url: str, supabase_anon_key: str) -> int:
    """Borra de job_listings lo mas viejo que 30 dias, para que la tabla no
    crezca sin limite."""
    response = requests.post(
        f"{supabase_url}/rest/v1/rpc/cleanup_old_job_listings",
        headers={
            "apikey": supabase_anon_key,
            "Authorization": f"Bearer {supabase_anon_key}",
            "Content-Type": "application/json",
        },
        json={},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
