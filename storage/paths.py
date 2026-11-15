import os
from pathlib import Path


def musiclist_home() -> Path:
    """Directory holding the database and HTTP cache.

    Defaults to ~/.musiclist so `music` sees the same pins and stars no
    matter which directory it runs from. Override with MUSICLIST_HOME.
    """
    home = Path(
        os.environ.get("MUSICLIST_HOME") or Path.home() / ".musiclist"
    ).expanduser()
    home.mkdir(parents=True, exist_ok=True)
    return home


def default_db_path() -> Path:
    return musiclist_home() / "musiclist.db"


def default_cache_dir() -> Path:
    return musiclist_home() / "cache"
