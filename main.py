#!/usr/bin/env python3

from datetime import date
from models import Venue
from storage import Cache, Database
from ui import Terminal
from venues_config import get_venues_config


def scrape_venue(venue_data, scraper_class, terminal, cache, db):
    """Scrape a single venue and return events"""
    venue = Venue(**venue_data)

    # Save venue to database
    db.save_venue(venue)
    terminal.show_info(f"Initialized venue: {venue.name}")

    # Create scraper
    scraper = scraper_class(venue, cache)

    # Scrape events with progress indicator
    with terminal.show_scraping_progress(venue.name):
        events = scraper.get_events()

    if events:
        # Filter out past events
        today = date.today()
        future_events = [event for event in events if event.date >= today]

        terminal.show_success(
            f"Found {len(future_events)} upcoming events from {venue.name}"
        )

        # Save to database
        new_count = db.save_events(events)  # Save all events to database
        terminal.show_info(f"Saved {new_count} new events to database")

        return future_events  # Return only future events for display
    else:
        terminal.show_error(f"No events found from {venue.name}")
        return []


def scrape_all_venues():
    """Main scraping function - scrapes all venues and displays results"""
    terminal = Terminal()
    terminal.show_header("🎵 Musiclist - Multi-Venue Scraper")

    # Initialize components
    cache = Cache()
    db = Database()

    # Get venues from centralized config
    venues_config = get_venues_config()

    all_events = []

    # Scrape all venues
    for config in venues_config:
        events = scrape_venue(
            config["venue_data"], config["scraper_class"], terminal, cache, db
        )
        all_events.extend(events)

    # Display summary
    if all_events:
        terminal.show_success(
            f"Total events found across all venues: {len(all_events)}"
        )

        # Display all events
        terminal.display_events(all_events)

        # Show sample output
        terminal.console.print("\n[dim]Sample events from all venues:[/dim]")
        for event in all_events[:10]:  # Show first 10
            date_str = event.date.strftime("%B %d, %Y")
            time_str = event.time.strftime("%I:%M %p") if event.time else "TBD"
            artists_str = ", ".join(event.artists)
            cost_str = f", {event.cost}" if event.cost else ""
            terminal.console.print(
                f"{date_str}, {artists_str}, {time_str}{cost_str}, {event.venue}, {event.url}"
            )

    else:
        terminal.show_error("No events found from any venue")
        terminal.show_info("This might be due to:")
        terminal.console.print("  • Website structure changes")
        terminal.console.print("  • Network connectivity issues")
        terminal.console.print("  • No upcoming events posted")


def main():
    """Entry point for main.py - backward compatibility"""
    scrape_all_venues()


if __name__ == "__main__":
    main()
