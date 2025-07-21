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
                    pinned BOOLEAN DEFAULT FALSE,
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
            self._migrate_add_pinned_column(conn)

            # Create pinned index after ensuring column exists
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_pinned ON events (pinned)"
            )

    def _migrate_add_cost_column(self, conn: sqlite3.Connection):
        """Add cost column to existing events table if it doesn't exist"""
        # Check if cost column exists
        cursor = conn.execute("PRAGMA table_info(events)")
        columns = [row[1] for row in cursor.fetchall()]

        if "cost" not in columns:
            conn.execute("ALTER TABLE events ADD COLUMN cost TEXT")

    def _migrate_add_pinned_column(self, conn: sqlite3.Connection):
        """Add pinned column to existing events table if it doesn't exist"""
        cursor = conn.execute("PRAGMA table_info(events)")
        columns = [row[1] for row in cursor.fetchall()]

        if "pinned" not in columns:
            conn.execute("ALTER TABLE events ADD COLUMN pinned BOOLEAN DEFAULT FALSE")

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
        """Save events, return count of new events added. Preserves pinned status for existing events."""
        if not events:
            return 0

        venue_name = events[0].venue
        venue_id = self.get_venue_id(venue_name)

        if not venue_id:
            raise ValueError(f"Venue {venue_name} not found in database")

        new_count = 0
        with self.get_connection() as conn:
            for event in events:
                # First, try to get existing event's pinned status
                existing = conn.execute(
                    """
                    SELECT id, pinned FROM events
                    WHERE venue_id = ? AND date = ? AND artists = ? AND url = ?
                    """,
                    (
                        venue_id,
                        event.date.isoformat(),
                        event.artists_display,
                        event.url,
                    ),
                ).fetchone()

                if existing:
                    # Update existing event but preserve pinned status
                    conn.execute(
                        """
                        UPDATE events
                        SET time = ?, cost = ?
                        WHERE id = ?
                        """,
                        (
                            event.time.isoformat() if event.time else None,
                            event.cost,
                            existing[0],
                        ),
                    )
                else:
                    # Insert new event
                    conn.execute(
                        """
                        INSERT INTO events (venue_id, date, time, artists, url, cost, pinned)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            venue_id,
                            event.date.isoformat(),
                            event.time.isoformat() if event.time else None,
                            event.artists_display,
                            event.url,
                            event.cost,
                            event.pinned,
                        ),
                    )
                    new_count += 1

            # Update last_scraped timestamp
            conn.execute(
                "UPDATE venues SET last_scraped = ? WHERE id = ?",
                (datetime.now().isoformat(), venue_id),
            )

        return new_count

    def get_recent_events(self, limit: int = 50) -> List[Event]:
        """Get recent events from database"""
        with self.get_connection() as conn:
            # Check if pinned column exists first
            cursor = conn.execute("PRAGMA table_info(events)")
            columns = [row[1] for row in cursor.fetchall()]
            has_pinned = "pinned" in columns

            if has_pinned:
                query = """
                    SELECT e.date, e.time, e.artists, v.name as venue, e.url, e.cost,
                           COALESCE(e.pinned, 0) as pinned, e.id
                    FROM events e
                    JOIN venues v ON e.venue_id = v.id
                    WHERE e.date >= date('now')
                    ORDER BY e.pinned DESC, e.date, e.time
                    LIMIT ?
                """
            else:
                query = """
                    SELECT e.date, e.time, e.artists, v.name as venue, e.url, e.cost,
                           0 as pinned, e.id
                    FROM events e
                    JOIN venues v ON e.venue_id = v.id
                    WHERE e.date >= date('now')
                    ORDER BY e.date, e.time
                    LIMIT ?
                """

            rows = conn.execute(query, (limit,)).fetchall()

            events = []
            for row in rows:
                try:
                    event_data = dict(row)
                    # Add created_at if missing (for compatibility)
                    if "created_at" not in event_data:
                        event_data["created_at"] = datetime.now().isoformat()
                    events.append(Event.from_dict(event_data))
                except Exception:
                    # Skip malformed events
                    continue

            return events

    def pin_event(self, event_id: int) -> bool:
        """Pin an event by ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE events SET pinned = TRUE WHERE id = ?", (event_id,)
            )
            return cursor.rowcount > 0

    def unpin_event(self, event_id: int) -> bool:
        """Unpin an event by ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE events SET pinned = FALSE WHERE id = ?", (event_id,)
            )
            return cursor.rowcount > 0

    def toggle_pin_event(self, event_id: int) -> bool:
        """Toggle pin status of an event by ID. Returns new pin status."""
        with self.get_connection() as conn:
            # Get current pin status
            row = conn.execute(
                "SELECT pinned FROM events WHERE id = ?", (event_id,)
            ).fetchone()

            if not row:
                return False

            current_pinned = bool(row[0])
            new_pinned = not current_pinned

            conn.execute(
                "UPDATE events SET pinned = ? WHERE id = ?", (new_pinned, event_id)
            )

            return new_pinned

    def find_event_by_details(
        self, date_str: str, artists: str, venue: str
    ) -> Optional[int]:
        """Find event ID by date, artists, and venue"""
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT e.id FROM events e
                JOIN venues v ON e.venue_id = v.id
                WHERE e.date = ? AND e.artists = ? AND v.name = ?
            """,
                (date_str, artists, venue),
            ).fetchone()

            return row[0] if row else None

    def get_pinned_events(self) -> List[Event]:
        """Get all pinned events"""
        with self.get_connection() as conn:
            # Check if pinned column exists first
            cursor = conn.execute("PRAGMA table_info(events)")
            columns = [row[1] for row in cursor.fetchall()]
            has_pinned = "pinned" in columns

            if not has_pinned:
                return []  # No pinned events if column doesn't exist yet

            rows = conn.execute(
                """
                SELECT e.date, e.time, e.artists, v.name as venue, e.url, e.cost,
                       e.pinned, e.id
                FROM events e
                JOIN venues v ON e.venue_id = v.id
                WHERE e.pinned = TRUE AND e.date >= date('now')
                ORDER BY e.date, e.time
            """,
            ).fetchall()

            events = []
            for row in rows:
                try:
                    event_data = dict(row)
                    if "created_at" not in event_data:
                        event_data["created_at"] = datetime.now().isoformat()
                    events.append(Event.from_dict(event_data))
                except Exception:
                    continue

            return events
