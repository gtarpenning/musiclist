#!/usr/bin/env python3
"""
Unified CLI for musiclist project

Provides both full venue scraping and filtered calendar views.
"""

import argparse
import sys
from datetime import date
from dateutil.relativedelta import relativedelta

from models import Venue
from storage import Cache, Database
from ui import CalendarDisplay, Terminal
from venues_config import (
    get_venues_config,
    star_venue,
    unstar_venue,
    get_venue_names,
)
from storage import Database


def scrape_venue(venue_data, scraper_class, terminal, cache, db):
    """Scrape a single venue and return events"""
    # Filter venue data to only include fields expected by Venue constructor
    venue_fields = {k: v for k, v in venue_data.items() if k != "scraper_class"}
    venue = Venue(**venue_fields)

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
    """Main scraping function - scrapes all venues and displays results using parallel processing"""
    terminal = Terminal()
    terminal.show_header("🎵 Musiclist - Multi-Venue Scraper")

    # Get venues from centralized config
    venues_config = get_venues_config()

    # Use parallel scraper for faster performance
    from utils.parallel import ParallelScraper
    from venues_config import DEFAULT_MAX_WORKERS

    parallel_scraper = ParallelScraper(max_workers=DEFAULT_MAX_WORKERS)

    # Scrape all venues in parallel with progress bar
    all_events, venue_stats = parallel_scraper.scrape_venues_parallel(
        venues_config, force_refresh=True
    )

    # Display summary
    if all_events:
        terminal.show_success(
            f"Total events found across all venues: {len(all_events)}"
        )

        # Display all events
        terminal.display_events(all_events)

        # Show sample output
        from ui.colors import style

        terminal.console.print(f"\n{style('Sample events from all venues:', 'dim')}")
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


def setup_parser():
    """Set up command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Musiclist - Multi-venue music event scraper for San Francisco",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      # Show calendar view (uses cached data if fresh)
  %(prog)s calendar             # Show events for current and next month
  %(prog)s calendar --force-refresh # Force scrape all venues (bypass cache)
  %(prog)s scrape               # Scrape all venues and show all events
  %(prog)s venue rickshaw       # Show events only from Rickshaw Stop (fuzzy matching)
  %(prog)s venue "great american" # Show events only from Great American Music Hall
  %(prog)s pin 5                # Pin event number 5
  %(prog)s pin "Arctic Monkeys" # Pin event by artist name
  %(prog)s unpin 3              # Unpin event number 3
  %(prog)s pinned               # Show all pinned events
  %(prog)s star warfield        # Star a venue (fuzzy matching)
  %(prog)s unstar warfield      # Unstar a venue
  %(prog)s starred              # Show events from starred venues + list starred venues
  %(prog)s --list-venues        # Show available venues
  %(prog)s --star-venue "The Warfield"     # Star a venue
  %(prog)s --unstar-venue "The Warfield"   # Unstar a venue

Data is cached for 24 hours. Pins are preserved during updates.
        """,
    )

    # Main commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Calendar command (default behavior)
    calendar_parser = subparsers.add_parser(
        "calendar",
        help="Show calendar view with events for current and next month (default)",
    )
    calendar_parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh by scraping all venues (bypasses 24-hour cache)",
    )

    # Venue filter command
    venue_parser = subparsers.add_parser(
        "venue", help="Show events from a specific venue (supports fuzzy matching)"
    )
    venue_parser.add_argument(
        "venue_name",
        help="Venue name (supports partial matches like 'rickshaw' for 'Rickshaw Stop')",
    )
    venue_parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh by scraping the venue (bypasses 24-hour cache)",
    )

    # Scrape command (full venue scraping)
    scrape_parser = subparsers.add_parser(
        "scrape", help="Scrape all venues and show all upcoming events"
    )

    # Pin command
    pin_parser = subparsers.add_parser(
        "pin", help="Pin an event by number or artist name"
    )
    pin_parser.add_argument("target", help="Event number or artist name to pin")

    # Unpin command
    unpin_parser = subparsers.add_parser(
        "unpin", help="Unpin an event by number or artist name"
    )
    unpin_parser.add_argument("target", help="Event number or artist name to unpin")

    # Star command
    star_parser = subparsers.add_parser(
        "star", help="Star a venue (supports fuzzy matching)"
    )
    star_parser.add_argument("venue_name", help="Venue name (supports partial matches)")

    # Unstar command
    unstar_parser = subparsers.add_parser(
        "unstar", help="Unstar a venue (supports fuzzy matching)"
    )
    unstar_parser.add_argument(
        "venue_name", help="Venue name (supports partial matches)"
    )

    # Show pinned command
    pinned_parser = subparsers.add_parser("pinned", help="Show all pinned events")

    # Show starred command
    starred_parser = subparsers.add_parser(
        "starred", help="Show events from starred venues + list starred venues"
    )

    # List venues option
    parser.add_argument(
        "--list-venues", action="store_true", help="List all available venues and exit"
    )

    # Venue starring options
    parser.add_argument(
        "--star-venue",
        metavar="VENUE_NAME",
        help="Star a venue (use quotes for names with spaces)",
    )

    parser.add_argument(
        "--unstar-venue",
        metavar="VENUE_NAME",
        help="Unstar a venue (use quotes for names with spaces)",
    )

    parser.add_argument(
        "--list-starred", action="store_true", help="List starred venues and exit"
    )

    return parser


def list_venues():
    """List all available venues"""
    venues = get_venue_names()
    db = Database()
    starred = db.get_starred_venues()

    print("🎵 Available Venues:")
    print()
    for i, venue in enumerate(venues, 1):
        star_indicator = " ⭐" if venue in starred else ""
        print(f"  {i}. {venue}{star_indicator}")
    print()
    print(f"Total: {len(venues)} venues enabled")
    if starred:
        print(f"Starred: {len(starred)} venues")


def list_starred_venues():
    """List starred venues"""
    db = Database()
    starred = db.get_starred_venues()

    if not starred:
        print("⭐ No venues are currently starred")
        print()
        print('💡 Tip: Use --star-venue "VENUE NAME" to star a venue')
        return

    print("⭐ Starred Venues:")
    print()
    for i, venue in enumerate(starred, 1):
        print(f"  {i}. {venue}")
    print()
    print(f"Total: {len(starred)} starred venues")


def handle_star_venue(venue_name: str):
    """Handle starring a venue"""
    success, message = star_venue(venue_name)
    if success:
        print(f"⭐ {message}")
    else:
        print(f"❌ {message}")
        # Show available venues if venue not found
        if "not found" in message.lower():
            print("\nAvailable venues:")
            for venue in get_venue_names():
                print(f"  - {venue}")


def handle_unstar_venue(venue_name: str):
    """Handle unstarring a venue"""
    success, message = unstar_venue(venue_name)
    if success:
        print(f"⭐ {message}")
    else:
        print(f"❌ {message}")


def get_event_by_number(event_number: int):
    """Get an event by its display number from the calendar view"""
    from datetime import datetime

    db = Database()
    events = db.get_recent_events(
        1000
    )  # Increase limit to get all events like calendar

    # Filter events the same way as calendar display
    calendar = CalendarDisplay()
    filtered_events = calendar.filter_events_by_date(events)

    # Sort all events reverse chronologically regardless of pin status (closest events at bottom)
    # Use event ID as secondary sort key for stable ordering when date/time are identical
    ordered_events = sorted(
        filtered_events,
        key=lambda e: (e.date, e.time or datetime.min.time(), e.id or 0),
        reverse=True,
    )

    # The event number is 1-based
    if 1 <= event_number <= len(ordered_events):
        return ordered_events[event_number - 1]

    return None


def find_event_by_artist_name(artist_name: str):
    """Find events by fuzzy matching artist name"""
    from datetime import datetime

    db = Database()
    events = db.get_recent_events(1000)  # Increase limit to match get_event_by_number

    # Filter events the same way as calendar display
    calendar = CalendarDisplay()
    filtered_events = calendar.filter_events_by_date(events)

    # Sort all events reverse chronologically regardless of pin status (closest events at bottom)
    # Use event ID as secondary sort key for stable ordering when date/time are identical
    ordered_events = sorted(
        filtered_events,
        key=lambda e: (e.date, e.time or datetime.min.time(), e.id or 0),
        reverse=True,
    )

    # Fuzzy search for artist name (case insensitive, partial match)
    artist_lower = artist_name.lower()
    matches = []

    for i, event in enumerate(ordered_events):
        for artist in event.artists:
            if artist_lower in artist.lower():
                matches.append((i + 1, event))  # 1-based indexing
                break

    return matches


def handle_pin_event(target: str):
    """Handle pinning an event by number or artist name"""

    # Try to parse as event number first
    try:
        event_number = int(target)
        event = get_event_by_number(event_number)
        if event:
            if event.pinned:
                print(
                    f"📌 Event #{event_number} is already pinned: {event.artists_display} at {event.venue}"
                )
                return

            if not event.id:
                print(f"❌ Cannot pin event #{event_number}: missing event ID")
                return

            db = Database()
            if db.pin_event(event.id):
                print(
                    f"📌 Pinned event #{event_number}: {event.artists_display} at {event.venue} on {event.date.strftime('%b %d')}"
                )
            else:
                print(f"❌ Failed to pin event #{event_number}")
            return
        else:
            print(f"❌ Event #{event_number} not found")
            return
    except ValueError:
        pass  # Not a number, try artist name search

    # Try to find by artist name
    matches = find_event_by_artist_name(target)
    if not matches:
        print(f"❌ No events found matching artist '{target}'")
        return

    if len(matches) == 1:
        event_number, event = matches[0]
        if event.pinned:
            print(
                f"📌 Event #{event_number} is already pinned: {event.artists_display} at {event.venue}"
            )
            return

        db = Database()
        if db.pin_event(event.id):
            print(
                f"📌 Pinned event #{event_number}: {event.artists_display} at {event.venue} on {event.date.strftime('%b %d')}"
            )
        else:
            print(f"❌ Failed to pin event #{event_number}")
    else:
        print(f"🔍 Found multiple events matching '{target}':")
        for event_number, event in matches:
            pin_status = "📌" if event.pinned else "  "
            print(
                f"  {pin_status} #{event_number}: {event.artists_display} at {event.venue} on {event.date.strftime('%b %d')}"
            )
        print(f"💡 Use event number to pin a specific event: music pin {matches[0][0]}")


def handle_unpin_event(target: str):
    """Handle unpinning an event by number or artist name"""

    # Try to parse as event number first
    try:
        event_number = int(target)
        event = get_event_by_number(event_number)
        if event:
            if not event.pinned:
                print(
                    f"📌 Event #{event_number} is not pinned: {event.artists_display} at {event.venue}"
                )
                return

            if not event.id:
                print(f"❌ Cannot unpin event #{event_number}: missing event ID")
                return

            db = Database()
            if db.unpin_event(event.id):
                print(
                    f"📌 Unpinned event #{event_number}: {event.artists_display} at {event.venue} on {event.date.strftime('%b %d')}"
                )
            else:
                print(f"❌ Failed to unpin event #{event_number}")
            return
        else:
            print(f"❌ Event #{event_number} not found")
            return
    except ValueError:
        pass  # Not a number, try artist name search

    # Try to find by artist name
    matches = find_event_by_artist_name(target)
    pinned_matches = [(num, event) for num, event in matches if event.pinned]

    if not pinned_matches:
        if matches:
            print(f"❌ Found events matching '{target}' but none are pinned")
        else:
            print(f"❌ No events found matching artist '{target}'")
        return

    if len(pinned_matches) == 1:
        event_number, event = pinned_matches[0]

        db = Database()
        if db.unpin_event(event.id):
            print(
                f"📌 Unpinned event #{event_number}: {event.artists_display} at {event.venue} on {event.date.strftime('%b %d')}"
            )
        else:
            print(f"❌ Failed to unpin event #{event_number}")
    else:
        print(f"🔍 Found multiple pinned events matching '{target}':")
        for event_number, event in pinned_matches:
            print(
                f"  📌 #{event_number}: {event.artists_display} at {event.venue} on {event.date.strftime('%b %d')}"
            )
        print(
            f"💡 Use event number to unpin a specific event: music unpin {pinned_matches[0][0]}"
        )


def find_venue_by_fuzzy_name(venue_input: str):
    """Find venue by fuzzy matching name"""
    venue_input_lower = venue_input.lower()
    available_venues = get_venue_names()

    # First try exact match
    for venue_name in available_venues:
        if venue_name.lower() == venue_input_lower:
            return venue_name

    # Then try partial matches
    matches = []
    for venue_name in available_venues:
        venue_lower = venue_name.lower()
        # Check if input is a substring of venue name
        if venue_input_lower in venue_lower:
            matches.append(venue_name)

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        return matches  # Return list for disambiguation

    # Try matching individual words
    venue_words = venue_input.lower().split()
    word_matches = []
    for venue_name in available_venues:
        venue_name_lower = venue_name.lower()
        if all(word in venue_name_lower for word in venue_words):
            word_matches.append(venue_name)

    if len(word_matches) == 1:
        return word_matches[0]
    elif len(word_matches) > 1:
        return word_matches

    return None


def handle_star_venue_command(venue_input: str):
    """Handle starring a venue with fuzzy matching"""
    venue_match = find_venue_by_fuzzy_name(venue_input)

    if venue_match is None:
        print(f"❌ No venue found matching '{venue_input}'")
        print("\nAvailable venues:")
        for venue in get_venue_names():
            print(f"  - {venue}")
        return

    if isinstance(venue_match, list):
        print(f"🔍 Multiple venues found matching '{venue_input}':")
        db = Database()
        starred_venues = db.get_starred_venues()
        for i, venue in enumerate(venue_match, 1):
            starred = " ⭐" if venue in starred_venues else ""
            print(f"  {i}. {venue}{starred}")
        print(
            f"💡 Be more specific: try 'music star {venue_match[0].split()[0].lower()}'"
        )
        return

    # Single match found
    success, message = star_venue(venue_match)
    if success:
        print(f"⭐ {message}")
    else:
        print(f"❌ {message}")


def handle_unstar_venue_command(venue_input: str):
    """Handle unstarring a venue with fuzzy matching"""
    venue_match = find_venue_by_fuzzy_name(venue_input)

    if venue_match is None:
        print(f"❌ No venue found matching '{venue_input}'")
        print("\nAvailable venues:")
        for venue in get_venue_names():
            print(f"  - {venue}")
        return

    if isinstance(venue_match, list):
        print(f"🔍 Multiple venues found matching '{venue_input}':")
        db = Database()
        starred_venues = db.get_starred_venues()
        for i, venue in enumerate(venue_match, 1):
            starred = " ⭐" if venue in starred_venues else ""
            print(f"  {i}. {venue}{starred}")
        print(
            f"💡 Be more specific: try 'music unstar {venue_match[0].split()[0].lower()}'"
        )
        return

    # Single match found
    success, message = unstar_venue(venue_match)
    if success:
        print(f"⭐ {message}")
    else:
        print(f"❌ {message}")


def show_starred_venues():
    """Show all starred venues"""
    calendar = CalendarDisplay()
    calendar.display_starred_venues_calendar()


def show_pinned_events():
    """Show all pinned events"""
    from ui import Terminal

    db = Database()
    pinned_events = db.get_pinned_events()

    if not pinned_events:
        print("📌 No events are currently pinned")
        print()
        print('💡 Tip: Use "music pin <number>" to pin an event from the calendar view')
        print('💡 Or use "music pin "Artist Name"" to pin by artist name')
        return

    terminal = Terminal()
    terminal.display_calendar_events(pinned_events, "📌 Your Pinned Events")


def show_calendar(force_refresh: bool = False):
    """Show calendar view (current and next month)"""
    calendar = CalendarDisplay()
    calendar.display_calendar(force_refresh=force_refresh)


def show_full_scrape():
    """Show full scraping results (all events)"""
    scrape_all_venues()


def show_venue_calendar(venue_name: str, force_refresh: bool = False):
    """Show calendar view filtered to a specific venue"""
    venue_match = find_venue_by_fuzzy_name(venue_name)

    if venue_match is None:
        print(f"❌ No venue found matching '{venue_name}'")
        print("\nAvailable venues:")
        for venue in get_venue_names():
            print(f"  - {venue}")
        return

    if isinstance(venue_match, list):
        print(f"🔍 Multiple venues found matching '{venue_name}':")
        db = Database()
        starred_venues = db.get_starred_venues()
        for i, venue in enumerate(venue_match, 1):
            starred = " ⭐" if venue in starred_venues else ""
            print(f"  {i}. {venue}{starred}")
        print(
            f"💡 Be more specific: try 'music venue {venue_match[0].split()[0].lower()}'"
        )
        return

    # Single match found - show calendar for this venue
    calendar = CalendarDisplay()
    calendar.display_venue_calendar(venue_match, force_refresh=force_refresh)


def main():
    """Main CLI entry point"""
    parser = setup_parser()
    args = parser.parse_args()

    # Handle venue starring options first
    if args.star_venue:
        handle_star_venue(args.star_venue)
        return

    if args.unstar_venue:
        handle_unstar_venue(args.unstar_venue)
        return

    if args.list_starred:
        list_starred_venues()
        return

    # Handle pinning subcommands
    if args.command == "pin":
        handle_pin_event(args.target)
        return

    if args.command == "unpin":
        handle_unpin_event(args.target)
        return

    if args.command == "pinned":
        show_pinned_events()
        return

    # Handle starring subcommands
    if args.command == "star":
        handle_star_venue_command(args.venue_name)
        return

    if args.command == "unstar":
        handle_unstar_venue_command(args.venue_name)
        return

    if args.command == "starred":
        show_starred_venues()
        return

    # Handle venue filtering command
    if args.command == "venue":
        force_refresh = getattr(args, "force_refresh", False)
        show_venue_calendar(args.venue_name, force_refresh=force_refresh)
        return

    # Handle list venues option
    if args.list_venues:
        list_venues()
        return

    # Default to calendar view if no command specified
    if args.command is None:
        show_calendar()
        return

    # Handle specific commands
    if args.command == "calendar":
        force_refresh = getattr(args, "force_refresh", False)
        show_calendar(force_refresh=force_refresh)
    elif args.command == "scrape":
        show_full_scrape()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
