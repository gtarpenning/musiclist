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


def setup_parser():
    """Set up command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Musiclist - Multi-venue music event scraper for San Francisco",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s calendar              # Show events for current and next month
  %(prog)s scrape               # Scrape all venues and show all events
  %(prog)s --list-venues        # Show available venues
  %(prog)s --star-venue "The Warfield"     # Star a venue
  %(prog)s --unstar-venue "The Warfield"   # Unstar a venue
  %(prog)s --list-starred       # List starred venues
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
