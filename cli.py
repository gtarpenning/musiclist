#!/usr/bin/env python3
"""
Unified CLI for musiclist project

Provides both full venue scraping and filtered calendar views.
"""

import argparse
import sys
import time

from storage import Cache, Database
from ui import CalendarDisplay, Terminal
from ui.calendar import event_numbers, numbered_calendar_events
from venues_config import (
    DEFAULT_MAX_WORKERS,
    fold,
    get_venue_names,
    get_venues_config,
    star_venue,
    unstar_venue,
)


def scrape_all_venues():
    """Force-refresh every venue and list all upcoming events (not just the calendar window)"""
    from utils.parallel import refresh_venues

    terminal = Terminal()
    terminal.show_header("🎵 Musiclist - Multi-Venue Scraper")

    db = Database()
    results = refresh_venues(
        get_venues_config(),
        force_refresh=True,
        max_workers=DEFAULT_MAX_WORKERS,
        db=db,
        console=terminal.console,
    )
    all_events = db.get_events(venues=get_venue_names())

    if all_events:
        terminal.show_success(
            f"Total upcoming events across all venues: {len(all_events)}"
        )
        terminal.display_events(all_events)
    else:
        terminal.show_error("No events found from any venue")
    terminal.display_venue_summary(
        {n: r.count for n, r in results.items()}, statuses=results
    )


def tls_hint(results, openssl_version=None):
    """Explain 403s that come from an outdated TLS stack rather than the site.

    Cloudflare-protected venue sites (Rickshaw Stop, as of 2026-11) reject
    OpenSSL 1.x handshakes whatever the headers, so on an old Python the
    venue fails every time while working fine on a current one.
    """
    import ssl

    openssl_version = openssl_version or ssl.OPENSSL_VERSION
    if not openssl_version.startswith("OpenSSL 1."):
        return None
    blocked = [name for name, r in results.items() if r.error and "HTTP 403" in r.error]
    if not blocked:
        return None
    return (
        f"{', '.join(blocked)} refused this Python's TLS stack "
        f"(Python {sys.version.split()[0]}, {openssl_version.split('  ')[0]}). "
        "Reinstall musiclist under Python 3.12+ (newer OpenSSL) to fix."
    )


def run_doctor(venue_filter: str = None) -> int:
    """Live health check: scrape each venue now (no caches, nothing saved) and report what parsed.

    Returns a process exit code: 0 if every checked venue produced upcoming events.
    """
    from rich.table import Table

    from ui.colors import style
    from utils.parallel import refresh_venues

    terminal = Terminal()
    configs = get_venues_config()
    if venue_filter:
        match = find_venue_by_fuzzy_name(venue_filter)
        names = match if isinstance(match, list) else [match] if match else []
        configs = [c for c in configs if c["name"] in names]
        if not configs:
            print(f"❌ No venue found matching '{venue_filter}'")
            return 2

    terminal.show_header(f"🩺 Scraper health check - {len(configs)} venues")
    started = time.time()
    results = refresh_venues(
        configs,
        force_refresh=True,
        max_workers=DEFAULT_MAX_WORKERS,
        console=terminal.console,
        cache=Cache(expiry_hours=0),
        save=False,
    )

    table = Table(show_header=True, header_style="bold")
    # Fixed columns never shrink; venue names truncate and errors wrap to fit narrow terminals
    table.add_column(
        "Venue", min_width=12, max_width=30, no_wrap=True, overflow="ellipsis"
    )
    table.add_column("Shows", justify="right", no_wrap=True, min_width=5)
    table.add_column("Through", no_wrap=True, min_width=10)
    table.add_column("Time%", justify="right", no_wrap=True, min_width=5)
    table.add_column("Price%", justify="right", no_wrap=True, min_width=6)
    table.add_column("Secs", justify="right", no_wrap=True, min_width=4)
    table.add_column("Status", min_width=6, ratio=1)

    failing = 0
    for cfg in configs:
        r = results[cfg["name"]]
        evs = r.events
        last = max((e.date for e in evs), default=None)
        pct = lambda n: f"{100 * n // len(evs)}" if evs else "-"
        if r.status == "fresh":
            status = style("ok", "success")
        else:
            failing += 1
            status = style(r.error or "site loaded, nothing parsed", "error")
        table.add_row(
            cfg["name"],
            str(len(evs)),
            last.strftime("%Y-%m-%d") if last else "-",
            pct(sum(1 for e in evs if e.time)),
            pct(sum(1 for e in evs if e.cost)),
            f"{r.elapsed:.1f}",
            status,
        )
    terminal.console.print(table)
    hint = tls_hint(results)
    if hint:
        terminal.show_warning(hint)
    total = sum(len(r.events) for r in results.values())
    summary = f"{total} upcoming shows from {len(configs) - failing}/{len(configs)} venues in {time.time() - started:.0f}s"
    (terminal.show_success if not failing else terminal.show_error)(summary)
    return 1 if failing else 0


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
  %(prog)s doctor               # Live-check every venue scraper (exit 1 if any broke)
  %(prog)s doctor chapel        # Live-check one venue
  %(prog)s venue rickshaw       # Show events only from Rickshaw Stop (fuzzy matching)
  %(prog)s rickshaw             # Same thing: any non-command word is a venue name
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

Data lives in ~/.musiclist (override with MUSICLIST_HOME) and is refreshed
every 24 hours. Pins and stars are preserved across refreshes.
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

    # Doctor command (live scraper health check)
    doctor_parser = subparsers.add_parser(
        "doctor", help="Scrape every venue live and report which scrapers are broken"
    )
    doctor_parser.add_argument(
        "venue_name", nargs="?", help="Only check venues matching this name"
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
    """Get an event by the number shown next to it in any calendar view"""
    ordered_events = numbered_calendar_events(Database())
    if 1 <= event_number <= len(ordered_events):
        return ordered_events[event_number - 1]
    return None


def find_event_by_artist_name(artist_name: str):
    """Find events by fuzzy (case/accent-insensitive, partial) artist match.

    Returns (number, event) pairs using the same numbers the calendar shows.
    """
    needle = fold(artist_name)
    return [
        (i, event)
        for i, event in enumerate(numbered_calendar_events(Database()), 1)
        if any(needle in fold(artist) for artist in event.artists)
    ]


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
    venue_input_lower = fold(venue_input.strip())
    available_venues = get_venue_names()

    # First try exact match (case- and accent-insensitive: "cafe du nord")
    for venue_name in available_venues:
        if fold(venue_name) == venue_input_lower:
            return venue_name

    # Then try partial matches
    matches = [v for v in available_venues if venue_input_lower in fold(v)]

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        return matches  # Return list for disambiguation

    # Try matching individual words
    venue_words = venue_input_lower.split()
    word_matches = []
    for venue_name in available_venues:
        venue_name_lower = fold(venue_name)
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
    """Show events from starred venues, then the starred list"""
    calendar = CalendarDisplay(db=Database())
    calendar.display_starred_venues_calendar()


def show_pinned_events():
    """Show all pinned events"""
    from ui import Terminal
    from ui.calendar import display_order

    db = Database()
    pinned_events = db.get_pinned_events()

    if not pinned_events:
        print("📌 No events are currently pinned")
        print()
        print('💡 Tip: Use "music pin <number>" to pin an event from the calendar view')
        print('💡 Or use "music pin "Artist Name"" to pin by artist name')
        return

    terminal = Terminal()
    terminal.display_calendar_events(
        display_order(pinned_events), "📌 Your Pinned Events", numbers=event_numbers(db)
    )


def show_calendar(force_refresh: bool = False):
    """Show calendar view (current and next month)"""
    calendar = CalendarDisplay(db=Database())
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
    calendar = CalendarDisplay(db=Database())
    calendar.display_venue_calendar(venue_match, force_refresh=force_refresh)


def venue_shortcut(argv, parser):
    """`music kilowatt` / `music great american` -> `music venue "<words>"`.

    Applies only when the first word isn't a subcommand or option, so every
    existing command parses exactly as before.
    """
    if not argv or argv[0].startswith("-"):
        return argv
    commands = set()
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            commands.update(action.choices)
    if argv[0] in commands:
        return argv
    words = [a for a in argv if not a.startswith("-")]
    flags = [a for a in argv if a.startswith("-")]
    return ["venue", " ".join(words)] + flags


def main(argv=None):
    """Main CLI entry point"""
    parser = setup_parser()
    argv = sys.argv[1:] if argv is None else list(argv)
    args = parser.parse_args(venue_shortcut(argv, parser))

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

    if args.command == "doctor":
        sys.exit(run_doctor(args.venue_name))

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
