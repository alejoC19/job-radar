from job_radar.dedup import SeenStore


def test_new_store_has_nothing_seen(tmp_path):
    store = SeenStore(tmp_path / "seen.json")
    assert not store.is_seen("https://example.com/job/1")


def test_mark_seen_and_check(tmp_path):
    store = SeenStore(tmp_path / "seen.json")
    store.mark_seen("https://example.com/job/1")
    assert store.is_seen("https://example.com/job/1")
    assert not store.is_seen("https://example.com/job/2")


def test_save_and_reload_persists_seen_urls(tmp_path):
    path = tmp_path / "seen.json"
    store = SeenStore(path)
    store.mark_seen("https://example.com/job/1")
    store.save()

    reloaded = SeenStore(path)
    assert reloaded.is_seen("https://example.com/job/1")
    assert not reloaded.is_seen("https://example.com/job/2")


def test_creates_parent_directories_on_save(tmp_path):
    path = tmp_path / "nested" / "dir" / "seen.json"
    store = SeenStore(path)
    store.mark_seen("https://example.com/job/1")
    store.save()
    assert path.exists()
