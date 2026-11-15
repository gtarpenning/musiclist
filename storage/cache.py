import hashlib
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .paths import default_cache_dir


class Cache:
    def __init__(self, cache_dir: Optional[str] = None, expiry_hours: int = 24):
        self.cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
        self.expiry_hours = expiry_hours
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, venue: str, url: str) -> str:
        """Generate cache key from venue and URL"""
        content = f"{venue}:{url}"
        return hashlib.md5(content.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get full path to cache file"""
        return self.cache_dir / f"{cache_key}.json"

    def _is_expired(self, cache_path: Path) -> bool:
        """Check if cache file is expired"""
        if not cache_path.exists():
            return True

        modified_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        expiry_time = modified_time + timedelta(hours=self.expiry_hours)
        return datetime.now() > expiry_time

    def get(self, venue: str, url: str) -> Optional[str]:
        """Get cached content if valid"""
        cache_path = self._get_cache_path(self._get_cache_key(venue, url))

        if self._is_expired(cache_path):
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f).get("content")
        except (OSError, json.JSONDecodeError):
            return None

    def set(self, venue: str, url: str, content: str):
        """Cache content with metadata (atomic write: scrapes run in parallel threads)"""
        cache_path = self._get_cache_path(self._get_cache_key(venue, url))
        data = {
            "venue": venue,
            "url": url,
            "content": content,
            "cached_at": datetime.now().isoformat(),
        }
        fd, tmp_path = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp_path, cache_path)
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def cleanup(self):
        """Remove expired cache files"""
        for cache_file in self.cache_dir.glob("*.json"):
            if self._is_expired(cache_file):
                cache_file.unlink()
