#!/usr/bin/env python3
"""
Unified CLI for musiclist project

Provides both full venue scraping and filtered calendar views.
"""

import argparse
import sys
from datetime import date
from dateutil.relativedelta import relativedelta

from main import scrape_all_venues
from music_calendar import CalendarDisplay
from venues_config import (
    get_enabled_venue_names,
    get_starred_venues,
    star_venue,
    unstar_venue,
    get_venue_by_name,
)
from storage import Database


def setup_parser():
    """Set up command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Musiclist - Multi-venue music event scraper for San Francisco",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      # Show calendar view (default)
  %(prog)s calendar             # Show events for current and next month
  %(prog)s scrape               # Scrape all venues and show all events
  %(prog)s pin 5                # Pin event number 5
  %(prog)s pin "Arctic Monkeys" # Pin event by artist name
  %(prog)s unpin 3              # Unpin event number 3
  %(prog)s pinned               # Show all pinned events
  %(prog)s --list-venues        # Show available venues
  %(prog)s --star-venue "The Warfield"     # Star a venue
  %(prog)s --unstar-venue "The Warfield"   # Unstar a venue
        """,
    )

    # Main commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Calendar command (default behavior)
    calendar_parser = subparsers.add_parser(
        "calendar",
        help="Show calendar view with events for current and next month (default)",
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

    # Show pinned command
    pinned_parser = subparsers.add_parser("pinned", help="Show all pinned events")

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
    venues = get_enabled_venue_names()
    starred = get_starred_venues()

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
    starred = get_starred_venues()

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
            for venue in get_enabled_venue_names():
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
    events = db.get_recent_events(50)  # Get same events as calendar view

    # Filter and sort events the same way as calendar display
    calendar = CalendarDisplay()
    filtered_events = calendar.filter_events_by_date(events)
    # Sort by pinned DESC (pinned first), then by date, then by time
    filtered_events.sort(
        key=lambda e: (not e.pinned, e.date, e.time or datetime.min.time())
    )

    # The event number is 1-based
    if 1 <= event_number <= len(filtered_events):
        return filtered_events[event_number - 1]

    return None


def find_event_by_artist_name(artist_name: str):
    """Find events by fuzzy matching artist name"""
    from datetime import datetime

    db = Database()
    events = db.get_recent_events(50)

    # Filter and sort events the same way as calendar display
    calendar = CalendarDisplay()
    filtered_events = calendar.filter_events_by_date(events)
    filtered_events.sort(
        key=lambda e: (not e.pinned, e.date, e.time or datetime.min.time())
    )

    # Fuzzy search for artist name (case insensitive, partial match)
    artist_lower = artist_name.lower()
    matches = []

    for i, event in enumerate(filtered_events):
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


def show_calendar():
    """Show calendar view (current and next month)"""
    calendar = CalendarDisplay()
    calendar.display_calendar()


def show_full_scrape():
    """Show full scraping results (all events)"""
    scrape_all_venues()


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
        show_calendar()
    elif args.command == "scrape":
        show_full_scrape()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
