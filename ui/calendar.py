from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import List, Dict

from models import Venue, Event
from storage import Cache, Database
from .terminal import Terminal
from venues_config import get_venues_config


class CalendarDisplay:
    def __init__(self):
        self.terminal = Terminal()
        self.cache = Cache()
        self.db = Database()

    def get_current_and_next_month_range(self):
        """Get date range for current month and next month"""
        today = date.today()
        current_month_start = today.replace(day=1)
        next_month_start = current_month_start + relativedelta(months=1)
        next_next_month_start = current_month_start + relativedelta(months=2)

        return current_month_start, next_next_month_start

    def filter_events_by_date(self, events: List[Event]) -> List[Event]:
        """Filter events to show only current and next month, and exclude past events"""
        today = date.today()
        start_date, end_date = self.get_current_and_next_month_range()

        return [
            event
            for event in events
            if event.date >= today and start_date <= event.date < end_date
        ]

    def scrape_venue(
        self, venue_data, scraper_class, force_refresh: bool = False
    ) -> List[Event]:
        """Scrape a single venue and return events. Uses cached data if fresh unless force_refresh is True."""
        # Filter venue_data to only include fields expected by Venue dataclass
        venue_fields = {
            "name": venue_data["name"],
            "base_url": venue_data["base_url"],
            "calendar_path": venue_data["calendar_path"],
        }
        venue = Venue(**venue_fields)
        venue_name = venue.name

        # Save venue to database (needed for cache checking)
        self.db.save_venue(venue)

        # Check if we have fresh cached data and don't need to scrape
        if not force_refresh and self.db.is_venue_data_fresh(
            venue_name, cache_hours=24
        ):
            # Use cached data - no need to scrape
            all_cached_events = self.db.get_cached_events_for_venue(venue_name)
            filtered_events = self.filter_events_by_date(all_cached_events)
            return filtered_events

        # Data is stale or force refresh requested - scrape fresh data
        scraper = scraper_class(venue, self.cache)

        # Scrape events with progress indicator
        events = scraper.get_events()
        if events:
            # Save all events to database (preserves existing pins)
            self.db.save_events(events)

            # Filter events for current and next month
            filtered_events = self.filter_events_by_date(events)
            return filtered_events
        else:
            # No events found from scraping, try cached data as fallback
            all_cached_events = self.db.get_cached_events_for_venue(venue_name)
            filtered_events = self.filter_events_by_date(all_cached_events)
            return filtered_events

    def scrape_all_venues(
        self, force_refresh: bool = False
    ) -> tuple[List[Event], Dict[str, int]]:
        """Scrape all venues and return filtered events plus venue statistics using parallel processing"""
        venues_config = get_venues_config()

        # Use parallel scraper for faster performance
        from utils.parallel import ParallelScraper
        from venues_config import DEFAULT_MAX_WORKERS

        parallel_scraper = ParallelScraper(max_workers=DEFAULT_MAX_WORKERS)

        # Scrape all venues in parallel with progress bar - this includes calendar date filtering
        all_events, venue_stats = parallel_scraper.scrape_venues_for_calendar(
            venues_config, force_refresh
        )

        return all_events, venue_stats

    def display_calendar(self, force_refresh: bool = False):
        """Main calendar display function"""
        start_date, end_date = self.get_current_and_next_month_range()
        title = f"🗓️  Music Calendar - {start_date.strftime('%B')} & {(start_date + relativedelta(months=1)).strftime('%B %Y')}"

        self.terminal.show_header(title)

        # Scrape all venues (using cache if fresh, unless force_refresh is True)
        all_events, venue_stats = self.scrape_all_venues(force_refresh)

        if not all_events:
            self.terminal.show_error("No events found for the current and next month")
            self.terminal.show_info(
                "Try running without date filtering to see all upcoming events"
            )
            return

        # Sort all events reverse chronologically with stable ordering (closest events at bottom)
        # Use event ID as secondary sort key for consistent numbering
        all_events.sort(
            key=lambda e: (e.date, e.time or datetime.min.time(), e.id or 0),
            reverse=True,
        )

        # Display all events together in chronological order with pin indicators
        self.terminal.display_calendar_events(all_events, "🗓️  Music Calendar")

        # Display venue summary
        self.terminal.display_venue_summary(venue_stats)

    def display_venue_calendar(self, venue_name: str, force_refresh: bool = False):
        """Display calendar view filtered to a specific venue"""
        start_date, end_date = self.get_current_and_next_month_range()

        # Find the venue configuration
        venues_config = get_venues_config()
        venue_config = None
        for config in venues_config:
            if config["name"] == venue_name:
                venue_config = config
                break

        if not venue_config:
            self.terminal.show_error(
                f"Venue configuration not found for '{venue_name}'"
            )
            return

        title = f"🎵 {venue_name} - {start_date.strftime('%B')} & {(start_date + relativedelta(months=1)).strftime('%B %Y')}"
        self.terminal.show_header(title)

        # Scrape only this venue
        events = self.scrape_venue(
            venue_config, venue_config["scraper_class"], force_refresh
        )

        if not events:
            self.terminal.show_error(
                f"No events found at {venue_name} for the current and next month"
            )
            self.terminal.show_info(
                f"This venue may not have events scheduled yet, or the scraper may need updating"
            )
            return

        # Sort all events reverse chronologically with stable ordering (closest events at bottom)
        # Use event ID as secondary sort key for consistent numbering
        events.sort(
            key=lambda e: (e.date, e.time or datetime.min.time(), e.id or 0),
            reverse=True,
        )

        # Display events with venue-specific title
        calendar_title = f"🎵 {venue_name} Events"
        self.terminal.display_calendar_events(events, calendar_title)

        # Display single venue summary
        venue_stats = {venue_name: len(events)}
        self.terminal.display_venue_summary(venue_stats)

        # Show venue filtering tip
        self.terminal.show_info(
            f"Showing events only from {venue_name}. Use 'music calendar' to see all venues."
        )

    def display_starred_venues_calendar(self, force_refresh: bool = False):
        """Display calendar view filtered to only starred venues, plus list of starred venues"""
        start_date, end_date = self.get_current_and_next_month_range()
        title = f"⭐ Starred Venues - {start_date.strftime('%B')} & {(start_date + relativedelta(months=1)).strftime('%B %Y')}"

        self.terminal.show_header(title)

        # Get starred venues
        starred_venues = self.db.get_starred_venues()

        if not starred_venues:
            self.terminal.show_error("No venues are currently starred")
            self.terminal.show_info('💡 Tip: Use "music star <venue>" to star a venue')
            return

        # Get venues config and filter to only starred venues
        venues_config = get_venues_config()
        starred_configs = [
            config for config in venues_config if config["name"] in starred_venues
        ]

        if not starred_configs:
            self.terminal.show_error("No starred venues found in configuration")
            return

        # Scrape only starred venues
        all_events = []
        venue_stats = {}

        for config in starred_configs:
            venue_name = config["name"]

            # Check if this venue will use cache before calling scrape_venue
            if not force_refresh and self.db.is_venue_data_fresh(
                venue_name, cache_hours=24
            ):
                pass  # Will use cache

            events = self.scrape_venue(config, config["scraper_class"], force_refresh)
            all_events.extend(events)
            venue_stats[config["name"]] = len(events)

        if not all_events:
            self.terminal.show_error(
                "No events found from starred venues for the current and next month"
            )
            self.terminal.show_info(
                "Your starred venues may not have events scheduled yet"
            )
        else:
            # Sort all events reverse chronologically with stable ordering (closest events at bottom)
            # Use event ID as secondary sort key for consistent numbering
            all_events.sort(
                key=lambda e: (e.date, e.time or datetime.min.time(), e.id or 0),
                reverse=True,
            )

            # Display events from starred venues
            self.terminal.display_calendar_events(
                all_events, "⭐ Events from Starred Venues"
            )

            # Display venue summary
            self.terminal.display_venue_summary(venue_stats)

        # Show list of starred venues below the events
        self.terminal.console.print("\n⭐ Your Starred Venues:")
        for i, venue in enumerate(starred_venues, 1):
            event_count = venue_stats.get(venue, 0)
            event_text = f" ({event_count} events)" if venue in venue_stats else ""
            self.terminal.console.print(f"  {i}. {venue}{event_text}")

        self.terminal.console.print(f"\nTotal: {len(starred_venues)} starred venues")
        self.terminal.show_info(
            'Use "music unstar <venue>" to unstar a venue or "music calendar" to see all venues'
        )
