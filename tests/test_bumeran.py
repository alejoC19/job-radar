import json
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from job_radar.sources.bumeran import BumeranScraper

FIXTURE_DATA = json.loads((Path(__file__).parent / "fixtures" / "bumeran_search.json").read_text(encoding="utf-8"))


def test_parse_item_builds_listing_from_public_job():
    scraper = BumeranScraper()
    item = FIXTURE_DATA["content"][0]

    listing = scraper._parse_item(item)

    assert listing.title == "Desarrollador/a de Software Jr"
    assert listing.company == "HIPODROMO PALERMO"
    assert listing.location == "Capital Federal, Buenos Aires"
    assert "híbrido" in listing.description.lower()
    assert listing.url == "https://www.bumeran.com.ar/empleos/desarrollador-a-de-software-jr-1118391216.html"
    assert listing.source == "bumeran"


def test_parse_item_uses_confidencial_company_and_extracts_salary():
    scraper = BumeranScraper()
    item = FIXTURE_DATA["content"][1]

    listing = scraper._parse_item(item)

    assert listing.company == "Confidencial"
    assert listing.salary_text == "$ 900.000 - $ 1.100.000"


def test_parse_item_returns_none_without_id_or_title():
    scraper = BumeranScraper()
    assert scraper._parse_item({"titulo": "Algo", "id": None}) is None
    assert scraper._parse_item({"id": 1, "titulo": ""}) is None


def test_fetch_sends_query_and_site_header_and_dedupes():
    scraper = BumeranScraper(search_terms=["desarrollador"], max_pages=2)

    first_page = Mock()
    first_page.raise_for_status = Mock()
    first_page.json = Mock(return_value=FIXTURE_DATA)
    empty_page = Mock()
    empty_page.raise_for_status = Mock()
    empty_page.json = Mock(return_value={"content": []})

    with patch("job_radar.sources.bumeran.requests.post", side_effect=[first_page, empty_page]) as mock_post, \
            patch("job_radar.sources.bumeran.time.sleep"):
        listings = scraper.fetch()

    assert len(listings) == 2
    assert mock_post.call_count == 2

    first_call = mock_post.call_args_list[0]
    assert first_call.kwargs["json"] == {"filtros": [], "query": "desarrollador"}
    assert first_call.kwargs["headers"]["x-site-id"] == "BMAR"
    assert first_call.kwargs["params"] == {"pageSize": 20, "page": 0, "sort": "RELEVANTES"}


def test_fetch_skips_term_on_request_error():
    scraper = BumeranScraper(search_terms=["desarrollador"], max_pages=2)

    with patch("job_radar.sources.bumeran.requests.post", side_effect=requests.RequestException("boom")):
        listings = scraper.fetch()

    assert listings == []
