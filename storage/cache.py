import os
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class Cache:
    def __init__(self, cache_dir: str = ".cache", expiry_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.expiry_hours = expiry_hours
        self.cache_dir.mkdir(exist_ok=True)

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
        cache_key = self._get_cache_key(venue, url)
        cache_path = self._get_cache_path(cache_key)

        if self._is_expired(cache_path):
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("content")
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def set(self, venue: str, url: str, content: str):
        """Cache content with metadata"""
        cache_key = self._get_cache_key(venue, url)
        cache_path = self._get_cache_path(cache_key)

        data = {
            "venue": venue,
            "url": url,
            "content": content,
            "cached_at": datetime.now().isoformat(),
        }

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def cleanup(self):
        """Remove expired cache files"""
        for cache_file in self.cache_dir.glob("*.json"):
            if self._is_expired(cache_file):
                cache_file.unlink()
