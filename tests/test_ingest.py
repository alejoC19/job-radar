from unittest.mock import Mock, patch

from job_radar.ingest import cleanup_old_listings, push_listings
from job_radar.models import JobListing


def test_push_listings_returns_zero_for_empty_list():
    assert push_listings("https://x.supabase.co", "anon-key", []) == 0


@patch("job_radar.ingest.requests.post")
def test_push_listings_posts_payload_to_rpc(mock_post):
    mock_post.return_value = Mock(raise_for_status=Mock(), json=Mock(return_value=2))
    listings = [
        JobListing(title="QA", company="Acme", url="https://example.com/1", source="fake"),
        JobListing(title="Dev", company="Beta", url="https://example.com/2", source="fake"),
    ]

    result = push_listings("https://x.supabase.co", "anon-key", listings)

    assert result == 2
    args, kwargs = mock_post.call_args
    assert args[0] == "https://x.supabase.co/rest/v1/rpc/ingest_job_listings"
    assert kwargs["headers"]["apikey"] == "anon-key"
    assert len(kwargs["json"]["payload"]) == 2
    assert kwargs["json"]["payload"][0]["url"] == "https://example.com/1"


@patch("job_radar.ingest.requests.post")
def test_cleanup_old_listings_calls_rpc(mock_post):
    mock_post.return_value = Mock(raise_for_status=Mock(), json=Mock(return_value=5))

    result = cleanup_old_listings("https://x.supabase.co", "anon-key")

    assert result == 5
    args, _ = mock_post.call_args
    assert args[0] == "https://x.supabase.co/rest/v1/rpc/cleanup_old_job_listings"
