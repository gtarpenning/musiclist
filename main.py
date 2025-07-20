#!/usr/bin/env python3

from models import Venue
from scrapers.brick_mortar import BrickMortarScraper
from scrapers.warfield import WarfieldScraper
from storage import Cache, Database
from ui import Terminal


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
        terminal.show_success(f"Found {len(events)} events from {venue.name}")

        # Save to database
        new_count = db.save_events(events)
        terminal.show_info(f"Saved {new_count} new events to database")

        return events
    else:
        terminal.show_error(f"No events found from {venue.name}")
        return []


def main():
    terminal = Terminal()
    terminal.show_header("🎵 Musiclist - Multi-Venue Scraper")

    # Initialize components
    cache = Cache()
    db = Database()

    # Define venues and their scrapers
    venues_config = [
        {
            "venue_data": {
                "name": "Brick & Mortar Music Hall",
                "base_url": "https://www.brickandmortarmusic.com",
                "calendar_path": "/calendar/",
            },
            "scraper_class": BrickMortarScraper,
        },
        {
            "venue_data": {
                "name": "The Warfield",
                "base_url": "https://www.thewarfieldtheatre.com",
                "calendar_path": "/events/",
            },
            "scraper_class": WarfieldScraper,
        },
    ]

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


if __name__ == "__main__":
    main()
