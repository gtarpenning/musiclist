import sqlite3
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from models import Event, Venue


class Database:
    def __init__(self, db_path: str = "musiclist.db"):
        self.db_path = Path(db_path)
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """Initialize database with schema"""
        with self.get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS venues (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    base_url TEXT NOT NULL,
                    calendar_path TEXT DEFAULT '/calendar/',
                    last_scraped TIMESTAMP,
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (venue_id) REFERENCES venues (id),
                    UNIQUE (venue_id, date, artists, url)
                );

                CREATE INDEX IF NOT EXISTS idx_events_date ON events (date);
                CREATE INDEX IF NOT EXISTS idx_events_venue ON events (venue_id);
            """
            )

            # Handle migration for existing databases
            self._migrate_add_cost_column(conn)

    def _migrate_add_cost_column(self, conn: sqlite3.Connection):
        """Add cost column to existing events table if it doesn't exist"""
        # Check if cost column exists
        cursor = conn.execute("PRAGMA table_info(events)")
        columns = [row[1] for row in cursor.fetchall()]

        if "cost" not in columns:
            conn.execute("ALTER TABLE events ADD COLUMN cost TEXT")

    def save_venue(self, venue: Venue) -> int:
        """Save venue and return ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT OR REPLACE INTO venues (name, base_url, calendar_path) VALUES (?, ?, ?)",
                (venue.name, venue.base_url, venue.calendar_path),
            )
            return cursor.lastrowid

    def get_venue_id(self, venue_name: str) -> Optional[int]:
        """Get venue ID by name"""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM venues WHERE name = ?", (venue_name,)
            ).fetchone()
            return row[0] if row else None

    def save_events(self, events: List[Event]) -> int:
        """Save events, return count of new events added"""
        if not events:
            return 0

        venue_name = events[0].venue
        venue_id = self.get_venue_id(venue_name)

        if not venue_id:
            raise ValueError(f"Venue {venue_name} not found in database")

        new_count = 0
        with self.get_connection() as conn:
            for event in events:
                try:
                    conn.execute(
                        """
                        INSERT INTO events (venue_id, date, time, artists, url, cost)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (
                            venue_id,
                            event.date.isoformat(),
                            event.time.isoformat() if event.time else None,
                            event.artists_display,
                            event.url,
                            event.cost,
                        ),
                    )
                    new_count += 1
                except sqlite3.IntegrityError:
                    # Event already exists
                    pass

            # Update last_scraped timestamp
            conn.execute(
                "UPDATE venues SET last_scraped = ? WHERE id = ?",
                (datetime.now().isoformat(), venue_id),
            )

        return new_count

    def get_recent_events(self, limit: int = 50) -> List[Event]:
        """Get recent events from database"""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT e.date, e.time, e.artists, v.name as venue, e.url, e.cost
                FROM events e
                JOIN venues v ON e.venue_id = v.id
                WHERE e.date >= date('now')
                ORDER BY e.date, e.time
                LIMIT ?
            """,
                (limit,),
            ).fetchall()

            events = []
            for row in rows:
                try:
                    events.append(Event.from_dict(dict(row)))
                except Exception:
                    # Skip malformed events
                    continue

            return events
