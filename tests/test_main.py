from unittest.mock import patch

from job_radar import main
from job_radar.models import JobListing
from job_radar.sources.base import Scraper


class FakeScraper(Scraper):
    name = "fake"

    def __init__(self, listings):
        self._listings = listings

    def fetch(self):
        return self._listings


def qa_listing(url="https://example.com/1") -> JobListing:
    return JobListing(
        title="QA Automation Engineer con Selenium y Playwright",
        company="Acme",
        url=url,
        description="Buscamos tester junior, remoto",
        source="fake",
    )


@patch("job_radar.main.send_document")
@patch("job_radar.main.send_message")
def test_run_notifies_new_listings_and_marks_them_seen(mock_send_message, mock_send_document, tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHAT_ID")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "SEEN_PATH", tmp_path / "seen.json")
    monkeypatch.setattr(main, "EXPORT_PATH", tmp_path / "avisos.xlsx")

    source = FakeScraper([qa_listing()])
    main.run([source])

    mock_send_message.assert_called_once()
    mock_send_document.assert_called_once()
    assert (tmp_path / "avisos.xlsx").exists()
    assert (tmp_path / "seen.json").exists()


@patch("job_radar.main.send_document")
@patch("job_radar.main.send_message")
def test_run_skips_already_seen_listings(mock_send_message, mock_send_document, tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "CHAT_ID")
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    monkeypatch.setattr(main, "SEEN_PATH", tmp_path / "seen.json")
    monkeypatch.setattr(main, "EXPORT_PATH", tmp_path / "avisos.xlsx")

    listing = qa_listing()
    main.run([FakeScraper([listing])])
    mock_send_message.reset_mock()
    mock_send_document.reset_mock()

    main.run([FakeScraper([listing])])

    mock_send_message.assert_not_called()
    mock_send_document.assert_not_called()
