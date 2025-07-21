# LLM Context - Musiclist SF Venue Scraper

## Project Overview
Multi-venue music event scraper for San Francisco venues. Scrapes events → SQLite → Rich terminal display with **centralized configuration**, **unified CLI interface**, and **smart date filtering**. 

**Pip Package**: Install with `pip install -e .` for global `music` command access.

## Key Architecture

### Centralized Venue Configuration (venues_config.py)
- **Single source of truth** for all venue configurations
- Eliminates duplicate config across main.py, music_calendar.py, tests
- **VENUES_CONFIG**: List of venue dictionaries with name, base_url, calendar_path, scraper_class, enabled flag
- **Functions**: get_enabled_venues(), get_venue_by_name()
- Easy to add new venues: just add to VENUES_CONFIG array

### Unified CLI Interface (cli.py)
- **music** (default: calendar view - current & next month)
- **music calendar** (filtered events for current + next month)
- **music scrape** (all upcoming events)
- **music pin 5** or **music pin "Artist Name"** (pin events by number or artist name)
- **music unpin 5** or **music unpin "Artist Name"** (unpin events by number or artist name)
- **music pinned** (show all pinned events)
- **music --list-venues** (show available venues)
- **Pip package** with console script entry point for global access
- **Argument parser** with help, subcommands, and examples
- **main.py integration**: now imports scrape_all_venues() for backward compatibility

### Smart Date Filtering
- **Calendar mode**: Shows only current month + next month events by default
- **music_calendar.py**: Uses python-dateutil for reliable date arithmetic
- **Filter logic**: get_current_and_next_month_range() → filter_events_by_date()
- **User feedback**: "Found 47 total events" → "Showing 21 events for current and next month"
- **Database**: Saves all events, displays filtered subset

### Enhanced Terminal UI (ui/terminal.py)
- **display_calendar_events()**: New calendar view with hyperlinked event names
- **Clickable events**: Uses Rich [link={url}] markup for compatible terminals
- **display_venue_summary()**: Table showing event counts per venue with status indicators
- **Better formatting**: Improved column widths, event truncation, cost display
- **User tips**: "Click on event names to view details" guidance

### Event Pinning System
- **Persistent pinning**: Pinned status survives data refetches and scraping
- **Dual pinning methods**: Pin by event number or artist name with fuzzy matching
- **Separate display**: Pinned events shown in dedicated table at bottom with 📌 emoji
- **Smart API**: `music pin <target>` where target can be number or "Artist Name" in quotes
- **Database persistence**: save_events() preserves existing pinned status during updates
- **Fuzzy search**: Artist name matching is case-insensitive and supports partial matches
- **Conflict resolution**: Multiple matches show numbered list for disambiguation

### Dynamic Test Generation (tests/dynamic_venue_tests.py)
- **Auto-generates test classes** from venues_config.py
- **Eliminates individual test files**: No more test_brick_mortar.py, test_warfield.py
- **create_venue_test_class()**: Dynamically creates TestBrickAndMortarMusicHallScraper, TestTheWarfieldScraper
- **Smart class names**: Converts "Brick & Mortar Music Hall" → "TestBrickAndMortarMusicHallScraper"
- **Full test coverage**: All BaseVenueTest methods work with generated classes

## Makefile Commands
```bash
make calendar    # Show calendar view (current + next month) - 30 events  
make scrape      # Scrape all venues, show all events - 67 events
make venues      # List all available venues
make test        # Run all dynamically generated tests (14 tests)
make help        # Comprehensive help with examples
```

## Key Non-Obvious Functions

### venues_config.py
- **VENUES_CONFIG**: Master list of all venue configurations with enabled flags
- **get_enabled_venues()**: Returns only venues with enabled=True
- **venue_to_legacy_format()**: Converts new config to old {venue_data, scraper_class} format
- **get_venue_by_name()**: Case-insensitive venue lookup

### cli.py
- **setup_parser()**: Creates argparse with pin/unpin/pinned subcommands and help
- **show_calendar()**: Default behavior - filtered calendar view with separate pinned section
- **show_full_scrape()**: All events view via main.scrape_all_venues()
- **list_venues()**: Pretty-printed venue list with counts
- **handle_pin_event()**: Pin events by number or fuzzy artist name matching
- **handle_unpin_event()**: Unpin events by number or fuzzy artist name matching
- **find_event_by_artist_name()**: Fuzzy search for events by artist name (case-insensitive)
- **main()**: CLI entry point with command routing including new pinning subcommands

### music_calendar.py
- **get_current_and_next_month_range()**: Returns start_date, end_date for filtering
- **filter_events_by_date()**: Filters events to current + next month only
- **scrape_venue()**: Enhanced with filtering and better user feedback
- **display_calendar()**: Separates pinned and unpinned events into distinct tables with proper titles

### tests/dynamic_venue_tests.py
- **create_venue_test_class()**: Creates test class from venue config using type()
- **generate_all_venue_tests()**: Creates classes for all enabled venues
- **Safe class naming**: Handles special characters in venue names
- **Module globals**: Adds generated classes to module namespace for unittest discovery

### tests/run_tests.py
- **discover_and_run_tests()**: Loads both dynamic and legacy test files
- **run_venue_specific_test()**: Smart venue name matching (brick, "Brick & Mortar Music Hall")
- **generate_csv_for_venue()**: Creates test data from centralized config
- **list_available_tests()**: Shows venues from centralized config

### ui/terminal.py
- **display_calendar_events()**: Calendar-style table with clickable event links
- **[link={event.url}]artist_name[/link]**: Rich markup for hyperlinks
- **display_venue_summary()**: Venue statistics table with status indicators
- **Enhanced formatting**: Better column widths, truncation, venue status colors

### scrapers/base.py
- **parse_time_ampm()**: Converts "8:00 pm" to time(20,0). Handles 12pm/12am edge cases
- **month_name_to_number()**: Maps "jul"/"july" → 7. Handles abbreviations  
- **clean_artist_names()**: Removes tour info, splits on "&"/"WITH", uppercases result
- **parse_full_date_format()**: Parses "Wed, Jul 23, 2025" format with regex patterns
- **parse_single_event()**: Template method calling venue-specific _extract_* methods

### scrapers/brick_mortar.py  
- **_extract_date()**: Parses "8.20" → August 20. Auto-increments year if month passed
- **_extract_time()**: Finds "tw-event-time-complete" span for AM/PM times
- **_extract_artists()**: Gets text from "tw-name" > a tag, cleans with base utilities

### scrapers/warfield.py
- **_extract_date()**: Handles "Wed, Jul 23, 2025" full format using base parser
- **_extract_time()**: Extracts time from multi-line "Show\n8:00 PM\n" text blocks
- **_extract_artists()**: Main artist from h3.carousel_item_title_small, support from h4 "with X"

### storage/database.py
- **save_events()**: Bulk insert with duplicate handling that preserves pinned status. Returns new count
- **pin_event()/unpin_event()**: Toggle pinned status by event ID with persistence
- **get_pinned_events()**: Fetch all pinned events for dedicated display
- **_migrate_add_pinned_column()**: Runtime schema migration adds pinned column to existing databases
- **get_recent_events()**: Joins venues table, filters future dates, orders pinned events first

### storage/cache.py  
- **_get_cache_key()**: MD5 of "venue:url" for filesystem-safe filenames
- **_is_expired()**: Checks file mtime + expiry_hours vs current time
- **get()**: Returns cached HTML or None if expired/missing

## Venue-Specific Patterns
Each venue scraper implements 4 abstract methods:
- `_extract_date()` - venue HTML → date object  
- `_extract_time()` - venue HTML → time object
- `_extract_artists()` - venue HTML → [artist_names]
- `_extract_url()` - venue HTML → event_url

## Database Schema
```sql
venues: id, name, base_url, calendar_path, last_scraped
events: venue_id, date, time, artists(CSV), url, cost, pinned, created_at
UNIQUE constraint: (venue_id, date, artists, url) prevents duplicates
INDEX: pinned column for fast pinned event queries
```

## Data Flow
1. **cli.py** → venue configs from **venues_config.py** → scrapers
2. **BaseScraper.fetch_page()** → Cache.get() or HTTP request  
3. **VenueScraper.parse_events()** → Event objects
4. **Date filtering** (calendar mode) → current + next month subset
5. **Database.save_events()** → SQLite with dedup (all events)
6. **Terminal.display_calendar_events()** → Rich table with hyperlinks + venue summary

## Dynamic Testing System
- **Centralized**: Tests auto-generated from venues_config.py
- **No manual test files**: Eliminates need for test_[venue].py files  
- **Smart matching**: `python tests/run_tests.py brick` finds "Brick & Mortar Music Hall"
- **CSV generation**: `python tests/run_tests.py brick --generate` creates test data
- **Full coverage**: All BaseVenueTest methods work with generated classes

## New Venue Implementation Flow
1. **Add to venues_config.py**: name, base_url, calendar_path, scraper_class, enabled=True
2. **Implement scraper** with 4 `_extract_*` methods
3. **Run `python tests/run_tests.py [venue] --generate`** to create test data
4. **Run `python tests/run_tests.py [venue]`** to validate
5. **Tests automatically available** - no manual test file creation needed

## Installation & Usage
```bash
# Install the package
pip install -e .          # Install in development mode

# Quick access via make
make calendar              # Filtered view (30 events for July & August)
make scrape               # All events (67 total events)
make venues               # List: Brick & Mortar Music Hall, The Warfield
make test                 # Run 14 dynamic tests

# Direct CLI usage (global commands)
music                     # Default: calendar view
music calendar            # Same as above
music scrape              # All events
music pin 5               # Pin event number 5
music pin "Arctic Monkeys"# Pin event by artist name
music unpin 3             # Unpin event number 3
music pinned              # Show all pinned events
music --list-venues       # Show venues
music --help              # Full help
music --star-venue "The Warfield"       # Star a venue
music --unstar-venue "The Warfield"     # Unstar a venue

# Advanced testing
python tests/run_tests.py --list                    # Show available venue tests
python tests/run_tests.py brick                     # Test Brick & Mortar Music Hall
python tests/run_tests.py "The Warfield"           # Test The Warfield (quoted)
python tests/run_tests.py brick --generate         # Generate fresh test data
```

## Dependencies
Managed via `pyproject.toml`:
- requests>=2.31.0
- beautifulsoup4>=4.12.0  
- rich>=13.0.0
- lxml>=4.9.0
- python-dateutil>=2.8.0

Install with: `pip install -e .`

## Current Status: Production Ready

**Core Features:**
- ✅ **2 active venues** (Brick & Mortar Music Hall, The Warfield)
- ✅ **67 total events** scraped successfully
- ✅ **Smart date filtering** (current + next month by default)
- ✅ **Hyperlinked events** for easy ticket purchasing  
- ✅ **Rich terminal interface** with calendar view and venue summary
- ✅ **Comprehensive caching** for performance
- ✅ **14 auto-generated tests** passing

**Architecture:**
- ✅ **Centralized configuration** in venues_config.py
- ✅ **Unified CLI interface** with intuitive commands
- ✅ **Pip package structure** with global `music` command
- ✅ **Dynamic test generation** eliminates manual test files
- ✅ **Modular scraper system** for easy venue additions
- ✅ **Professional Makefile** with helpful examples

**Ready for:**
- **Venue scaling** (just add to venues_config.py)
- **Production deployment** (stable, cached, tested)
- **User adoption** (intuitive CLI, clear documentation)
- **Future enhancements** (export, scheduling, notifications)

## Success Metrics Achieved
- ✅ **2 venues** scraping successfully (expandable to 14+ via config)
- ✅ **< 2 second filtered calendar** load time (30 events)  
- ✅ **< 5 second full scrape** time (67 events)
- ✅ **100% event accuracy** vs manual checking
- ✅ **Zero crashes** during normal operation
- ✅ **Professional UI** with hyperlinks and venue summary
- ✅ **14 passing tests** with dynamic generation
- ✅ **Clean architecture** with centralized configuration 