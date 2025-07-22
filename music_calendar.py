#!/usr/bin/env python3

from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import List, Dict

from models import Venue, Event
from storage import Cache, Database
from ui import Terminal
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
        venue = Venue(**venue_data)
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
        """Scrape all venues and return filtered events plus venue statistics"""
        venues_config = get_venues_config()
        all_events = []
        venue_stats = {}
        cached_venues = []
        scraped_venues = []

        for config in venues_config:
            venue_name = config["venue_data"]["name"]

            # Check if this venue will use cache before calling scrape_venue
            if not force_refresh and self.db.is_venue_data_fresh(
                venue_name, cache_hours=24
            ):
                cached_venues.append(venue_name)
            else:
                scraped_venues.append(venue_name)

            events = self.scrape_venue(
                config["venue_data"], config["scraper_class"], force_refresh
            )
            all_events.extend(events)
            venue_stats[config["venue_data"]["name"]] = len(events)

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

        # Sort all events chronologically with stable ordering
        # Use event ID as secondary sort key for consistent numbering
        all_events.sort(
            key=lambda e: (e.date, e.time or datetime.min.time(), e.id or 0)
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
            if config["venue_data"]["name"] == venue_name:
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
            venue_config["venue_data"], venue_config["scraper_class"], force_refresh
        )

        if not events:
            self.terminal.show_error(
                f"No events found at {venue_name} for the current and next month"
            )
            self.terminal.show_info(
                f"This venue may not have events scheduled yet, or the scraper may need updating"
            )
            return

        # Sort all events chronologically with stable ordering
        # Use event ID as secondary sort key for consistent numbering
        events.sort(key=lambda e: (e.date, e.time or datetime.min.time(), e.id or 0))

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


def main():
    calendar = CalendarDisplay()
    calendar.display_calendar()


if __name__ == "__main__":
    main()
