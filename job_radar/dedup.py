from __future__ import annotations

import json
from pathlib import Path


class SeenStore:
    """Guarda las URLs de avisos ya notificados para no repetirlos entre corridas."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._seen: set[str] = set()
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._seen = set(data.get("urls", []))

    def is_seen(self, url: str) -> bool:
        return url in self._seen

    def mark_seen(self, url: str) -> None:
        self._seen.add(url)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"urls": sorted(self._seen)}
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
