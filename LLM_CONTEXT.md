# LLM Context - Musiclist SF Venue Scraper

## Project Overview
Multi-venue music event scraper for San Francisco venues. Scrapes events → SQLite → Rich terminal display.

## Key Non-Obvious Functions

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
- **save_events()**: Bulk insert with UNIQUE constraint duplicate handling. Returns new count
- **_migrate_add_cost_column()**: Runtime schema migration for existing databases
- **get_recent_events()**: Joins venues table, filters future dates only

### storage/cache.py  
- **_get_cache_key()**: MD5 of "venue:url" for filesystem-safe filenames
- **_is_expired()**: Checks file mtime + expiry_hours vs current time
- **get()**: Returns cached HTML or None if expired/missing

### ui/terminal.py
- **show_scraping_progress()**: Rich Progress context manager with spinner
- **display_events()**: Rich Table with date formatting, artist truncation, cost display

### tests/base_venue.py (Core Testing Engine)
- **BaseVenueTest**: CSV-driven testing framework. Just set 4 class vars: VENUE_NAME, SCRAPER_CLASS, BASE_URL, CALENDAR_PATH
- **_load_events_from_csv()**: Loads test data from `tests/data/[venue]_expected.csv`
- **generate_csv_file()**: Creates CSV from actual scraper results
- **_csv_row_to_event()/_event_to_csv_row()**: CSV ↔ Event object conversion
- **test_csv_roundtrip()**: Validates Event → CSV → Event integrity
- **test_database_roundtrip()**: Validates Event.to_dict() ↔ Event.from_dict()

### tests/run_tests.py (Advanced Test Runner)
- **--generate flag**: `python tests/run_tests.py brick_mortar --generate` runs actual scraper and creates CSV
- **generate_csv_for_venue()**: Live scraping → CSV file generation for test data
- **run_individual_test()**: Run specific test methods, e.g. `brick_mortar test_csv_data_loads`
- **--list**: Shows all available test venues
- **Rich output**: Color-coded results, failure details, test summary tables

## Venue-Specific Patterns
Each venue scraper implements 4 abstract methods:
- `_extract_date()` - venue HTML → date object  
- `_extract_time()` - venue HTML → time object
- `_extract_artists()` - venue HTML → [artist_names]
- `_extract_url()` - venue HTML → event_url

## Database Schema
```sql
venues: id, name, base_url, calendar_path, last_scraped
events: venue_id, date, time, artists(CSV), url, cost, created_at
UNIQUE constraint: (venue_id, date, artists, url) prevents duplicates
```

## Data Flow
1. main.py → venue configs → scrapers
2. BaseScraper.fetch_page() → Cache.get() or HTTP request  
3. VenueScraper.parse_events() → Event objects
4. Database.save_events() → SQLite with dedup
5. Terminal.display_events() → Rich table output

## CSV Test Data System
- `tests/data/[venue_name]_expected.csv` contains scraped results
- Generated via `--generate` flag, not manually written
- Format: date,time,artists,venue,url,cost
- Enables data-driven testing without hardcoded expectations

## New Venue Implementation Flow
1. Copy `tests/test_template.py` → `tests/test_[venue].py`
2. Set 4 class variables (VENUE_NAME, SCRAPER_CLASS, BASE_URL, CALENDAR_PATH)
3. Implement scraper with 4 `_extract_*` methods
4. Run `python tests/run_tests.py [venue] --generate` to create test data
5. Run `python tests/run_tests.py [venue]` to validate

## Testing Commands
```bash
python tests/run_tests.py                      # All tests
python tests/run_tests.py --list               # Show available venues  
python tests/run_tests.py brick_mortar         # Venue-specific tests
python tests/run_tests.py brick_mortar --generate  # Generate test CSV from live scraping
python tests/run_tests.py brick_mortar test_csv_roundtrip  # Specific test method
```

## Planned Features (Empty Directories)
- `export/` - iCal export functionality (planned)
- `config/` - Venue configuration management (planned) 