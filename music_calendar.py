#!/usr/bin/env python3

from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import List, Dict

from models import Venue, Event
from storage import Cache, Database
from ui import Terminal
from venues_config import get_legacy_venues_config


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
        """Filter events to show only current and next month"""
        start_date, end_date = self.get_current_and_next_month_range()
        
        return [
            event for event in events 
            if start_date <= event.date < end_date
        ]

    def scrape_venue(self, venue_data, scraper_class) -> List[Event]:
        """Scrape a single venue and return events"""
        venue = Venue(**venue_data)
        
        # Save venue to database
        self.db.save_venue(venue)
        
        # Create scraper
        scraper = scraper_class(venue, self.cache)
        
        # Scrape events with progress indicator
        with self.terminal.show_scraping_progress(venue.name):
            events = scraper.get_events()
        
        if events:
            # Filter events for current and next month
            filtered_events = self.filter_events_by_date(events)
            
            self.terminal.show_success(f"Found {len(events)} total events from {venue.name}")
            if len(filtered_events) != len(events):
                self.terminal.show_info(f"Showing {len(filtered_events)} events for current and next month")
                
            # Save all events to database (not just filtered ones)
            new_count = self.db.save_events(events)
            self.terminal.show_info(f"Saved {new_count} new events to database")
            
            return filtered_events
        else:
            self.terminal.show_error(f"No events found from {venue.name}")
            return []

    def scrape_all_venues(self) -> tuple[List[Event], Dict[str, int]]:
        """Scrape all venues and return filtered events plus venue statistics"""
        venues_config = get_legacy_venues_config()
        all_events = []
        venue_stats = {}

        for config in venues_config:
            events = self.scrape_venue(
                config["venue_data"], config["scraper_class"]
            )
            all_events.extend(events)
            venue_stats[config["venue_data"]["name"]] = len(events)

        return all_events, venue_stats

    def display_calendar(self):
        """Main calendar display function"""
        start_date, end_date = self.get_current_and_next_month_range()
        title = f"🗓️  Music Calendar - {start_date.strftime('%B')} & {(start_date + relativedelta(months=1)).strftime('%B %Y')}"
        
        self.terminal.show_header(title)
        
        # Scrape all venues
        all_events, venue_stats = self.scrape_all_venues()
        
        if not all_events:
            self.terminal.show_error("No events found for the current and next month")
            self.terminal.show_info("Try running without date filtering to see all upcoming events")
            return
        
        # Sort events by date and time
        all_events.sort(key=lambda e: (e.date, e.time or datetime.min.time()))
        
        # Display calendar view
        self.terminal.display_calendar_events(all_events)
        
        # Display venue summary
        self.terminal.display_venue_summary(venue_stats)


def main():
    calendar = CalendarDisplay()
    calendar.display_calendar()


if __name__ == "__main__":
    main() 