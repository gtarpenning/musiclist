#!/usr/bin/env python3

from models import Venue
from scrapers.brick_mortar import BrickMortarScraper
from storage import Cache, Database
from ui import Terminal


def main():
    terminal = Terminal()
    terminal.show_header("🎵 Musiclist MVP - Brick & Mortar")

    # Initialize components
    cache = Cache()
    db = Database()

    # Create Brick & Mortar venue
    venue = Venue(
        name="Brick & Mortar Music Hall",
        base_url="https://www.brickandmortarmusic.com",
        calendar_path="/calendar/",
    )

    # Save venue to database
    db.save_venue(venue)
    terminal.show_info(f"Initialized venue: {venue.name}")

    # Create scraper
    scraper = BrickMortarScraper(venue, cache)

    # Scrape events with progress indicator
    with terminal.show_scraping_progress(venue.name):
        events = scraper.get_events()

    if events:
        terminal.show_success(f"Found {len(events)} events")

        # Save to database
        new_count = db.save_events(events)
        terminal.show_info(f"Saved {new_count} new events to database")

        # Display events
        terminal.display_events(events)

        # Test output format (matching test.txt)
        terminal.console.print("\n[dim]Reference format output:[/dim]")
        for event in events[:5]:  # Show first 5
            date_str = (
                event.date.strftime("%B %d").replace(" 0", " ").replace(" ", " ") + "th"
            )
            time_str = event.time.strftime("%I:%M%p").upper() if event.time else "TBD"
            artists_str = ", ".join(event.artists)
            cost_str = f", {event.cost}" if event.cost else ""
            terminal.console.print(
                f"{date_str}, {artists_str}, {time_str}{cost_str}, {event.url}"
            )

    else:
        terminal.show_error("No events found")
        terminal.show_info("This might be due to:")
        terminal.console.print("  • Website structure changes")
        terminal.console.print("  • Network connectivity issues")
        terminal.console.print("  • No upcoming events posted")


if __name__ == "__main__":
    main()
