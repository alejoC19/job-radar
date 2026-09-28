from pathlib import Path
from unittest.mock import Mock, patch

import requests

from job_radar.sources.computrabajo import ComputrabajoScraper

FIXTURE_HTML = (Path(__file__).parent / "fixtures" / "computrabajo_search.html").read_text(encoding="utf-8")


def test_parse_extracts_listing_without_company_link():
    scraper = ComputrabajoScraper()
    listings = scraper._parse(FIXTURE_HTML)

    plain = next(listing for listing in listings if "Mobile" in listing.title)
    assert plain.title == "Desarrollador/a Mobile"
    assert plain.company == "Importante empresa del sector salud"
    assert plain.location == "Belgrano, Capital Federal"
    assert "remoto" in plain.description.lower()
    assert plain.salary_text is None
    assert plain.source == "computrabajo"
    assert plain.url.startswith("https://ar.computrabajo.com/ofertas-de-trabajo/")


def test_parse_extracts_listing_with_company_link_and_salary():
    scraper = ComputrabajoScraper()
    listings = scraper._parse(FIXTURE_HTML)

    verified = next(listing for listing in listings if "Fullstack" in listing.title)
    assert verified.company == "ADN - Recursos Humanos"
    assert verified.location == "Recoleta, Capital Federal"
    assert verified.salary_text == "$ 2.222,00"


def test_parse_returns_two_listings():
    scraper = ComputrabajoScraper()
    assert len(scraper._parse(FIXTURE_HTML)) == 2


def test_fetch_paginates_until_empty_page_and_dedupes():
    scraper = ComputrabajoScraper(search_terms=["desarrollador"], max_pages=3)

    empty_page = "<div class='box_list'></div>"
    mock_responses = [Mock(text=FIXTURE_HTML), Mock(text=empty_page)]
    for r in mock_responses:
        r.raise_for_status = Mock()

    with patch("job_radar.sources.computrabajo.requests.get", side_effect=mock_responses) as mock_get, \
            patch("job_radar.sources.computrabajo.time.sleep"):
        listings = scraper.fetch()

    assert mock_get.call_count == 2
    assert len(listings) == 2
    first_call_url = mock_get.call_args_list[0].args[0]
    assert first_call_url == "https://ar.computrabajo.com/trabajo-de-desarrollador"
    second_call_url = mock_get.call_args_list[1].args[0]
    assert second_call_url == "https://ar.computrabajo.com/trabajo-de-desarrollador?p=2"


def test_fetch_skips_term_on_request_error():
    scraper = ComputrabajoScraper(search_terms=["desarrollador"], max_pages=2)

    with patch("job_radar.sources.computrabajo.requests.get", side_effect=requests.RequestException("boom")):
        listings = scraper.fetch()

    assert listings == []
