from unittest.mock import MagicMock, mock_open, patch

from job_radar.models import JobListing, ScoreResult
from job_radar.notifier import format_top10_message, send_document, send_message


def make_listing(**overrides) -> JobListing:
    defaults = dict(title="QA Tester", company="Acme", url="https://example.com/1")
    defaults.update(overrides)
    return JobListing(**defaults)


def test_format_top10_message_includes_title_company_score_link():
    listing = make_listing(title="QA Automation Engineer", company="Acme")
    result = ScoreResult(profile_key="qa", profile_name="QA Automation", score=9)

    message = format_top10_message([(listing, result)])

    assert "QA Automation Engineer" in message
    assert "Acme" in message
    assert "9" in message
    assert "QA Automation" in message
    assert listing.url in message


def test_format_top10_message_includes_salary_when_present():
    listing = make_listing(salary_text="$500.000 - $700.000")
    result = ScoreResult(profile_key="qa", profile_name="QA Automation", score=9)

    message = format_top10_message([(listing, result)])
    assert "$500.000 - $700.000" in message


def test_format_top10_message_limits_to_ten():
    pairs = [
        (make_listing(title=f"Aviso {i}", url=f"https://example.com/{i}"), ScoreResult("qa", "QA", i))
        for i in range(15)
    ]
    message = format_top10_message(pairs)
    assert message.count("https://example.com/") == 10


def test_format_top10_message_escapes_html_special_chars():
    listing = make_listing(title="QA <Senior> & Tester")
    result = ScoreResult(profile_key="qa", profile_name="QA Automation", score=9)
    message = format_top10_message([(listing, result)])
    assert "<Senior>" not in message
    assert "&lt;Senior&gt;" in message


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
