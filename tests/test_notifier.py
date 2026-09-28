from unittest.mock import MagicMock, mock_open, patch

from job_radar.models import JobListing, ScoreResult
from job_radar.notifier import format_messages, send_document, send_message


def make_listing(**overrides) -> JobListing:
    defaults = dict(title="QA Tester", company="Acme", url="https://example.com/1")
    defaults.update(overrides)
    return JobListing(**defaults)


def test_format_messages_includes_title_company_score_link():
    listing = make_listing(title="QA Automation Engineer", company="Acme")
    result = ScoreResult(profile_key="qa", profile_name="QA Automation", score=9)

    messages = format_messages([(listing, result)])

    assert len(messages) == 1
    assert "QA Automation Engineer" in messages[0]
    assert "Acme" in messages[0]
    assert "9" in messages[0]
    assert "QA Automation" in messages[0]
    assert listing.url in messages[0]


def test_format_messages_includes_salary_when_present():
    listing = make_listing(salary_text="$500.000 - $700.000")
    result = ScoreResult(profile_key="qa", profile_name="QA Automation", score=9)

    messages = format_messages([(listing, result)])
    assert "$500.000 - $700.000" in messages[0]


def test_format_messages_includes_every_listing_not_just_top_ten():
    pairs = [
        (make_listing(title=f"Aviso {i}", url=f"https://example.com/{i}"), ScoreResult("qa", "QA", i))
        for i in range(35)
    ]
    messages = format_messages(pairs)
    assert sum(m.count("https://example.com/") for m in messages) == 35


def test_format_messages_splits_into_multiple_messages_when_too_long():
    pairs = [
        (make_listing(title=f"Aviso con un titulo bastante largo numero {i}", url=f"https://example.com/{i}"),
         ScoreResult("qa", "QA", i))
        for i in range(60)
    ]
    messages = format_messages(pairs)

    assert len(messages) > 1
    for message in messages:
        assert len(message) <= 4096
    assert "parte 1/" in messages[0]


def test_format_messages_returns_friendly_message_when_no_listings():
    messages = format_messages([])
    assert len(messages) == 1
    assert "No hay avisos nuevos" in messages[0]


def test_format_messages_escapes_html_special_chars():
    listing = make_listing(title="QA <Senior> & Tester")
    result = ScoreResult(profile_key="qa", profile_name="QA Automation", score=9)
    messages = format_messages([(listing, result)])
    assert "<Senior>" not in messages[0]
    assert "&lt;Senior&gt;" in messages[0]


@patch("job_radar.notifier.requests.post")
def test_send_message_posts_to_telegram_api(mock_post):
    mock_post.return_value = MagicMock(raise_for_status=MagicMock())

    send_message("TOKEN", "CHAT_ID", "hola")

    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.telegram.org/botTOKEN/sendMessage"
    assert kwargs["json"]["chat_id"] == "CHAT_ID"
    assert kwargs["json"]["text"] == "hola"


@patch("job_radar.notifier.requests.post")
@patch("builtins.open", new_callable=mock_open, read_data=b"fake-excel-bytes")
def test_send_document_posts_file_to_telegram_api(mock_file, mock_post):
    mock_post.return_value = MagicMock(raise_for_status=MagicMock())

    send_document("TOKEN", "CHAT_ID", "avisos.xlsx", caption="hoy")

    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.telegram.org/botTOKEN/sendDocument"
    assert kwargs["data"]["chat_id"] == "CHAT_ID"
    assert kwargs["data"]["caption"] == "hoy"
    assert "document" in kwargs["files"]
