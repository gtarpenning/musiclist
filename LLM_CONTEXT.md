# LLM Context - SF Music Calendar

## Project Overview
Multi-venue music event scraper for San Francisco. Scrapes 13 venues → SQLite → Rich terminal UI with date filtering and event pinning. Pip package with global `music` command.

## Architecture

### Core Components
- **venues_config.py**: Centralized config for all 13 venues with scraper classes
- **cli.py**: Unified interface with calendar/scrape/pin commands  
- **models/**: Event and Venue data models
- **scrapers/**: 13 venue-specific scrapers inheriting from BaseScraper
- **storage/**: SQLite database and HTTP caching
- **ui/**: Rich terminal interface with clickable events
- **tests/**: Dynamic test generation from venue config

### Key Features
- **Smart filtering**: Calendar mode shows current + next month only
- **Event pinning**: Pin/unpin events by number or artist name with fuzzy matching
- **Venue starring**: Star favorite venues for priority display
- **Caching**: HTTP caching to avoid repeated requests
- **Hyperlinked events**: Clickable event names in compatible terminals

## CLI Commands
```bash
music                    # Calendar view (filtered)
music calendar           # Same as above
music scrape            # All upcoming events
music pin 5             # Pin event by number
music pin "Artist"      # Pin by artist name
music unpin 3           # Unpin event
music pinned            # Show pinned events
music --list-venues     # List all venues
music --star-venue "Venue"    # Star venue
music --unstar-venue "Venue"  # Unstar venue
```

## Database Schema
```sql
venues: id, name, base_url, calendar_path, starred, last_scraped
events: venue_id, date, time, artists, url, cost, pinned, created_at
UNIQUE: (venue_id, date, artists, url) prevents duplicates
```

## Scraper Pattern
Each venue implements 4 methods:
- `_extract_date()`: HTML → date object
- `_extract_time()`: HTML → time object  
- `_extract_artists()`: HTML → artist list
- `_extract_url()`: HTML → event URL

## Dynamic Testing
- **Auto-generated tests** from venues_config.py
- **No manual test files** needed
- **CSV test data generation**: `python tests/run_tests.py [venue] --generate`
- **Smart venue matching**: `python tests/run_tests.py brick` finds "Brick & Mortar Music Hall"

## Installation
```bash
pip install -e .        # Install package
make calendar           # Filtered events
make scrape            # All events  
make test              # Run all tests
```

## Current Status
- **13 venues**: All major SF music venues supported
- **Production ready**: Stable, cached, tested
- **Rich UI**: Terminal interface with hyperlinks and colors
- **Persistent data**: SQLite storage with event pinning
- **Package**: v0.1.9 with proper pip installation

## Dependencies
- requests, beautifulsoup4, rich, lxml, python-dateutil
- Managed via pyproject.toml

## Adding New Venues
1. Add to VENUES_CONFIG in venues_config.py
2. Implement scraper with 4 extract methods
3. Generate test data with `--generate` flag
4. Tests auto-created, no manual files needed 