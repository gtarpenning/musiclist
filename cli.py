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
from venues_config import get_enabled_venue_names


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
        """
    )
    
    # Main commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Calendar command (default behavior)
    calendar_parser = subparsers.add_parser(
        'calendar',
        help='Show calendar view with events for current and next month (default)'
    )
    
    # Scrape command (full venue scraping)
    scrape_parser = subparsers.add_parser(
        'scrape', 
        help='Scrape all venues and show all upcoming events'
    )
    
    # List venues option
    parser.add_argument(
        '--list-venues',
        action='store_true',
        help='List all available venues and exit'
    )
    
    return parser


def list_venues():
    """List all available venues"""
    venues = get_enabled_venue_names()
    print("🎵 Available Venues:")
    print()
    for i, venue in enumerate(venues, 1):
        print(f"  {i}. {venue}")
    print()
    print(f"Total: {len(venues)} venues enabled")


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
    
    # Handle list venues option
    if args.list_venues:
        list_venues()
        return
    
    # Default to calendar view if no command specified
    if args.command is None:
        show_calendar()
        return
    
    # Handle specific commands
    if args.command == 'calendar':
        show_calendar()
    elif args.command == 'scrape':
        show_full_scrape()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main() 