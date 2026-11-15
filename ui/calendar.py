from datetime import date, datetime
from typing import Dict, List, Optional

from dateutil.relativedelta import relativedelta

from models import Event
from storage import Cache, Database
from venues_config import DEFAULT_MAX_WORKERS, get_venue_names, get_venues_config

from .terminal import Terminal


def calendar_window(today: Optional[date] = None):
    """[first day of this month, first day of the month after next)"""
    today = today or date.today()
    start = today.replace(day=1)
    return start, start + relativedelta(months=2)


def display_order(events: List[Event]) -> List[Event]:
    """Reverse chronological (closest show at the bottom, next to the prompt), stable on id."""
    return sorted(
        events,
        key=lambda e: (e.date, e.time or datetime.min.time(), e.id or 0),
        reverse=True,
    )


def numbered_calendar_events(db: Database) -> List[Event]:
    """The canonical numbered list behind `music pin <n>`: every configured venue's
    events in the calendar window, in display order. Number = index + 1."""
    start, end = calendar_window()
    return display_order(db.get_events(start, end, venues=get_venue_names()))


def event_numbers(db: Database) -> Dict[int, int]:
    return {
        e.id: i
        for i, e in enumerate(numbered_calendar_events(db), 1)
        if e.id is not None
    }


class CalendarDisplay:
    def __init__(self, db: Optional[Database] = None, cache: Optional[Cache] = None):
        self.terminal = Terminal()
        self.db = db or Database()
        self.cache = cache or Cache()

    def get_current_and_next_month_range(self):
        """Get date range for current month and next month"""
        return calendar_window()

    def filter_events_by_date(self, events: List[Event]) -> List[Event]:
        """Filter events to show only current and next month, and exclude past events"""
        today = date.today()
        start_date, end_date = calendar_window()
        return [
            e for e in events if e.date >= today and start_date <= e.date < end_date
        ]

    def refresh(self, venue_configs, force_refresh: bool = False):
        from utils.parallel import refresh_venues

        return refresh_venues(
            venue_configs,
            force_refresh=force_refresh,
            max_workers=DEFAULT_MAX_WORKERS,
            db=self.db,
            cache=self.cache,
            console=self.terminal.console,
        )

    def _title_months(self) -> str:
        start, _ = calendar_window()
        return f"{start.strftime('%B')} & {(start + relativedelta(months=1)).strftime('%B %Y')}"

    def _show(self, events: List[Event], title: str, results) -> None:
        numbers = event_numbers(self.db)
        self.terminal.display_calendar_events(
            display_order(events), title, numbers=numbers
        )
        self.terminal.display_venue_summary(
            {name: r.count for name, r in results.items()},
            statuses={name: r for name, r in results.items()},
        )

    def display_calendar(self, force_refresh: bool = False):
        """Main calendar display function"""
        self.terminal.show_header(f"🗓️  Music Calendar - {self._title_months()}")
        results = self.refresh(get_venues_config(), force_refresh)

        start, end = calendar_window()
        events = self.db.get_events(start, end, venues=get_venue_names())
        if not events:
            self.terminal.show_error("No events found for the current and next month")
            self.terminal.display_venue_summary(
                {n: r.count for n, r in results.items()}, statuses=results
            )
            return

        self._show(events, "🗓️  Music Calendar", results)

    def display_venue_calendar(self, venue_name: str, force_refresh: bool = False):
        """Display calendar view filtered to a specific venue"""
        venue_config = next(
            (c for c in get_venues_config() if c["name"] == venue_name), None
        )
        if not venue_config:
            self.terminal.show_error(
                f"Venue configuration not found for '{venue_name}'"
            )
            return

        self.terminal.show_header(f"🎵 {venue_name} - {self._title_months()}")
        results = self.refresh([venue_config], force_refresh)

        start, end = calendar_window()
        events = self.db.get_events(start, end, venues=[venue_name])
        if not events:
            result = results.get(venue_name)
            self.terminal.show_error(
                f"No events found at {venue_name} for the current and next month"
            )
            if result and result.status == "error":
                self.terminal.show_info(f"Fetch failed: {result.error}")
            elif result and result.status == "empty":
                self.terminal.show_info(
                    "The site loaded but no shows parsed; run `music doctor` to check the scraper"
                )
            return

        self._show(events, f"🎵 {venue_name} Events", results)
        self.terminal.show_info(
            f"Showing events only from {venue_name}. Use 'music calendar' to see all venues."
        )

    def display_starred_venues_calendar(self, force_refresh: bool = False):
        """Display calendar view filtered to only starred venues, plus list of starred venues"""
        self.terminal.show_header(f"⭐ Starred Venues - {self._title_months()}")

        configured = set(get_venue_names())
        starred_venues = [v for v in self.db.get_starred_venues() if v in configured]
        if not starred_venues:
            self.terminal.show_error("No venues are currently starred")
            self.terminal.show_info('💡 Tip: Use "music star <venue>" to star a venue')
            return

        starred_configs = [
            c for c in get_venues_config() if c["name"] in starred_venues
        ]
        results = self.refresh(starred_configs, force_refresh)

        start, end = calendar_window()
        events = self.db.get_events(start, end, venues=starred_venues)
        if events:
            self._show(events, "⭐ Events from Starred Venues", results)
        else:
            self.terminal.show_error(
                "No events found from starred venues for the current and next month"
            )

        self.terminal.console.print("\n⭐ Starred Venues:")
        counts = {}
        for e in events:
            counts[e.venue] = counts.get(e.venue, 0) + 1
        for i, venue in enumerate(starred_venues, 1):
            self.terminal.console.print(
                f"  {i}. {venue} ({counts.get(venue, 0)} events)"
            )
        self.terminal.console.print(f"\nTotal: {len(starred_venues)} starred venues")
        self.terminal.show_info(
            'Use "music unstar <venue>" to unstar a venue or "music calendar" to see all venues'
        )
