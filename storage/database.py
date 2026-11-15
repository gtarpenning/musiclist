import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, List, Optional

from models import Event, Venue

from .paths import default_db_path

_EVENT_COLUMNS = """
    e.date, e.time, e.artists, v.name as venue, e.url, e.cost,
    COALESCE(e.pinned, 0) as pinned, e.id, e.created_at
"""


def _today() -> str:
    # SQLite's date('now') is UTC, which in San Francisco hides tonight's
    # shows from ~4pm onward. Always compare against the local date.
    return date.today().isoformat()


class Database:
    def __init__(self, db_path: Optional[str] = None):
        is_default = db_path is None
        self.db_path = Path(db_path) if db_path else default_db_path()
        is_new = not self.db_path.exists()
        self.init_database()
        if is_default and is_new:
            self._import_legacy_from_cwd()

    @contextmanager
    def connect(self):
        """Connection that commits on success, rolls back on error, and always closes."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # Kept for callers/tests that used the old name
    get_connection = connect

    def init_database(self):
        """Initialize database with schema (and upgrade older databases in place)"""
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS venues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    base_url TEXT NOT NULL,
                    calendar_path TEXT DEFAULT '/calendar/',
                    last_scraped TIMESTAMP,
                    starred BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    venue_id INTEGER NOT NULL,
                    date DATE NOT NULL,
                    time TIME,
                    artists TEXT NOT NULL,
                    url TEXT NOT NULL,
                    cost TEXT,
                    pinned BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (venue_id) REFERENCES venues (id),
                    UNIQUE (venue_id, date, artists, url)
                );

                CREATE INDEX IF NOT EXISTS idx_events_date ON events (date);
                CREATE INDEX IF NOT EXISTS idx_events_venue ON events (venue_id);
                """
            )
            event_cols = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
            if "pinned" not in event_cols:
                conn.execute(
                    "ALTER TABLE events ADD COLUMN pinned BOOLEAN DEFAULT FALSE"
                )
            if "cost" not in event_cols:
                conn.execute("ALTER TABLE events ADD COLUMN cost TEXT")
            venue_cols = {row[1] for row in conn.execute("PRAGMA table_info(venues)")}
            if "starred" not in venue_cols:
                conn.execute(
                    "ALTER TABLE venues ADD COLUMN starred BOOLEAN DEFAULT FALSE"
                )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_pinned ON events (pinned)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_venues_starred ON venues (starred)"
            )

    # ------------------------------------------------------------------ legacy import

    def _import_legacy_from_cwd(self):
        """Older versions kept musiclist.db in whatever directory `music` ran from.
        On first run, carry stars and upcoming pins over from one found in the CWD."""
        legacy = Path.cwd() / "musiclist.db"
        try:
            if legacy.exists() and legacy.resolve() != self.db_path.resolve():
                self.import_legacy(legacy)
        except Exception:
            pass  # A broken legacy file must never stop the app from starting

    def import_legacy(self, legacy_path) -> dict:
        """Import starred venues and upcoming pinned events from another database file."""
        src = sqlite3.connect(f"file:{legacy_path}?mode=ro", uri=True)
        src.row_factory = sqlite3.Row
        try:
            venue_cols = {row[1] for row in src.execute("PRAGMA table_info(venues)")}
            event_cols = {row[1] for row in src.execute("PRAGMA table_info(events)")}
            stars = []
            if "starred" in venue_cols:
                stars = [
                    dict(r)
                    for r in src.execute(
                        "SELECT name, base_url, calendar_path FROM venues WHERE starred"
                    )
                ]
            pins = []
            if "pinned" in event_cols:
                pins = [
                    dict(r)
                    for r in src.execute(
                        """SELECT e.date, e.time, e.artists, e.url, e.cost,
                                   v.name, v.base_url, v.calendar_path
                            FROM events e JOIN venues v ON e.venue_id = v.id
                            WHERE e.pinned AND e.date >= ?""",
                        (_today(),),
                    )
                ]
        finally:
            src.close()

        for row in stars:
            self.save_venue(
                Venue(row["name"], row["base_url"], row["calendar_path"] or "/")
            )
            self.star_venue(row["name"])

        with self.connect() as conn:
            for row in pins:
                venue_id = self.save_venue(
                    Venue(row["name"], row["base_url"], row["calendar_path"] or "/")
                )
                conn.execute(
                    """INSERT OR IGNORE INTO events (venue_id, date, time, artists, url, cost, pinned)
                       VALUES (?, ?, ?, ?, ?, ?, 1)""",
                    (
                        venue_id,
                        row["date"],
                        row["time"],
                        row["artists"],
                        row["url"],
                        row["cost"],
                    ),
                )
        return {"stars": len(stars), "pins": len(pins)}

    # ------------------------------------------------------------------ venues

    def save_venue(self, venue: Venue) -> int:
        """Save venue and return ID, preserving last_scraped timestamp"""
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM venues WHERE name = ?", (venue.name,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE venues SET base_url = ?, calendar_path = ? WHERE id = ?",
                    (venue.base_url, venue.calendar_path, existing[0]),
                )
                return existing[0]
            cursor = conn.execute(
                "INSERT INTO venues (name, base_url, calendar_path) VALUES (?, ?, ?)",
                (venue.name, venue.base_url, venue.calendar_path),
            )
            return cursor.lastrowid

    def get_venue_id(self, venue_name: str) -> Optional[int]:
        """Get venue ID by name"""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id FROM venues WHERE name = ?", (venue_name,)
            ).fetchone()
            return row[0] if row else None

    def is_venue_data_fresh(self, venue_name: str, cache_hours: int = 24) -> bool:
        """Check if venue data is fresh (scraped within cache_hours)"""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT last_scraped FROM venues WHERE name = ?", (venue_name,)
            ).fetchone()

        if not row or not row[0]:
            return False
        try:
            age = datetime.now() - datetime.fromisoformat(row[0])
            return age.total_seconds() < cache_hours * 3600
        except (ValueError, TypeError):
            return False

    def get_last_scraped(self, venue_name: str) -> Optional[datetime]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT last_scraped FROM venues WHERE name = ?", (venue_name,)
            ).fetchone()
        try:
            return datetime.fromisoformat(row[0]) if row and row[0] else None
        except ValueError:
            return None

    def star_venue(self, venue_name: str) -> bool:
        """Star a venue by name"""
        with self.connect() as conn:
            return (
                conn.execute(
                    "UPDATE venues SET starred = TRUE WHERE name = ?", (venue_name,)
                ).rowcount
                > 0
            )

    def unstar_venue(self, venue_name: str) -> bool:
        """Unstar a venue by name"""
        with self.connect() as conn:
            return (
                conn.execute(
                    "UPDATE venues SET starred = FALSE WHERE name = ?", (venue_name,)
                ).rowcount
                > 0
            )

    def get_starred_venues(self) -> List[str]:
        """Get list of starred venue names"""
        with self.connect() as conn:
            return [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM venues WHERE starred = TRUE ORDER BY name"
                )
            ]

    def is_venue_starred(self, venue_name: str) -> bool:
        """Check if a venue is starred"""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT starred FROM venues WHERE name = ?", (venue_name,)
            ).fetchone()
            return bool(row[0]) if row else False

    # ------------------------------------------------------------------ events

    @staticmethod
    def _rows_to_events(rows) -> List[Event]:
        events = []
        for row in rows:
            data = dict(row)
            if not data.get("created_at"):
                data["created_at"] = datetime.now().isoformat()
            else:
                data["created_at"] = str(data["created_at"]).replace(" ", "T")
            data["pinned"] = bool(data.get("pinned"))
            try:
                events.append(Event.from_dict(data))
            except Exception:
                continue  # Skip malformed rows
        return events

    def save_events(self, events: List[Event], prune_missing: bool = False) -> int:
        """Upsert events for one venue; return count of new rows.

        Pinned status of existing rows is preserved. With prune_missing, any
        upcoming unpinned event for the venue that is absent from `events` is
        deleted: it was cancelled, or the listing changed shape (renamed act,
        new URL), and keeping it would show stale or duplicate shows.
        """
        if not events:
            return 0

        venue_name = events[0].venue
        venue_id = self.get_venue_id(venue_name)
        if not venue_id:
            raise ValueError(f"Venue {venue_name} not found in database")

        new_count = 0
        seen_ids = []
        with self.connect() as conn:
            for event in events:
                params = (
                    venue_id,
                    event.date.isoformat(),
                    event.artists_display,
                    event.url,
                )
                existing = conn.execute(
                    "SELECT id FROM events WHERE venue_id = ? AND date = ? AND artists = ? AND url = ?",
                    params,
                ).fetchone()
                event_time = event.time.isoformat() if event.time else None
                if existing:
                    conn.execute(
                        "UPDATE events SET time = ?, cost = ? WHERE id = ?",
                        (event_time, event.cost, existing[0]),
                    )
                    seen_ids.append(existing[0])
                else:
                    cursor = conn.execute(
                        """INSERT INTO events (venue_id, date, time, artists, url, cost, pinned)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        params[:2]
                        + (
                            event_time,
                            event.artists_display,
                            event.url,
                            event.cost,
                            event.pinned,
                        ),
                    )
                    seen_ids.append(cursor.lastrowid)
                    new_count += 1

            if prune_missing:
                conn.execute(
                    "CREATE TEMP TABLE IF NOT EXISTS _seen (id INTEGER PRIMARY KEY)"
                )
                conn.execute("DELETE FROM _seen")
                conn.executemany(
                    "INSERT OR IGNORE INTO _seen (id) VALUES (?)",
                    ((i,) for i in seen_ids),
                )
                conn.execute(
                    """DELETE FROM events
                       WHERE venue_id = ? AND date >= ? AND COALESCE(pinned, 0) = 0
                         AND id NOT IN (SELECT id FROM _seen)""",
                    (venue_id, _today()),
                )

            conn.execute(
                "UPDATE venues SET last_scraped = ? WHERE id = ?",
                (datetime.now().isoformat(), venue_id),
            )

        return new_count

    def mark_scraped(self, venue_name: str):
        """Record a successful scrape that found nothing (so we don't re-hit the site for 24h)."""
        with self.connect() as conn:
            conn.execute(
                "UPDATE venues SET last_scraped = ? WHERE name = ?",
                (datetime.now().isoformat(), venue_name),
            )

    def get_events(
        self,
        start: Optional[date] = None,
        end: Optional[date] = None,
        venues: Optional[Iterable[str]] = None,
        pinned_only: bool = False,
    ) -> List[Event]:
        """Upcoming events in [start, end), optionally limited to some venues."""
        start = max(start or date.today(), date.today())
        clauses = ["e.date >= ?"]
        params: list = [start.isoformat()]
        if end:
            clauses.append("e.date < ?")
            params.append(end.isoformat())
        if pinned_only:
            clauses.append("e.pinned")
        if venues is not None:
            venues = list(venues)
            if not venues:
                return []
            clauses.append(f"v.name IN ({','.join('?' * len(venues))})")
            params.extend(venues)
        query = f"""
            SELECT {_EVENT_COLUMNS}
            FROM events e JOIN venues v ON e.venue_id = v.id
            WHERE {' AND '.join(clauses)}
            ORDER BY e.date, e.time, e.id
        """
        with self.connect() as conn:
            return self._rows_to_events(conn.execute(query, params).fetchall())

    def get_cached_events_for_venue(self, venue_name: str) -> List[Event]:
        """Get upcoming events for a specific venue"""
        return self.get_events(venues=[venue_name])

    def get_recent_events(self, limit: Optional[int] = None) -> List[Event]:
        """Get upcoming events from database (pinned first, then by date)"""
        events = self.get_events()
        events.sort(key=lambda e: not e.pinned)
        return events[:limit] if limit else events

    def get_pinned_events(self) -> List[Event]:
        """Get all upcoming pinned events"""
        return self.get_events(pinned_only=True)

    def pin_event(self, event_id: int) -> bool:
        """Pin an event by ID"""
        with self.connect() as conn:
            return (
                conn.execute(
                    "UPDATE events SET pinned = TRUE WHERE id = ?", (event_id,)
                ).rowcount
                > 0
            )

    def unpin_event(self, event_id: int) -> bool:
        """Unpin an event by ID"""
        with self.connect() as conn:
            return (
                conn.execute(
                    "UPDATE events SET pinned = FALSE WHERE id = ?", (event_id,)
                ).rowcount
                > 0
            )

    def toggle_pin_event(self, event_id: int) -> bool:
        """Toggle pin status of an event by ID. Returns new pin status."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT pinned FROM events WHERE id = ?", (event_id,)
            ).fetchone()
            if not row:
                return False
            new_pinned = not bool(row[0])
            conn.execute(
                "UPDATE events SET pinned = ? WHERE id = ?", (new_pinned, event_id)
            )
            return new_pinned

    def find_event_by_details(
        self, date_str: str, artists: str, venue: str
    ) -> Optional[int]:
        """Find event ID by date, artists, and venue"""
        with self.connect() as conn:
            row = conn.execute(
                """SELECT e.id FROM events e JOIN venues v ON e.venue_id = v.id
                   WHERE e.date = ? AND e.artists = ? AND v.name = ?""",
                (date_str, artists, venue),
            ).fetchone()
            return row[0] if row else None
