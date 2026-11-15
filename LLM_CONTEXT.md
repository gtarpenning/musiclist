# LLM Context - SF Music Calendar

## Project Overview
Multi-venue music event scraper for San Francisco. Scrapes 27 venues → SQLite → Rich terminal UI with date filtering, event pinning and venue starring. Pip package (`sf-music-calendar`) with a global `music` command.

## Architecture

### Core Components
- **venues_config.py**: `VENUES_CONFIG`, one dict per venue (name, base_url, calendar_path, scraper_class), plus star/lookup helpers (`fold()` makes matching accent- and case-insensitive)
- **cli.py**: argparse front end; `music <words>` that isn't a subcommand is treated as `music venue "<words>"`
- **models/**: `Event` and `Venue` dataclasses
- **scrapers/**: shared platform scrapers plus a few venue-specific ones, all on `BaseScraper`
- **storage/**: SQLite (`database.py`), page cache (`cache.py`), data dir (`paths.py`)
- **utils/parallel.py**: `refresh_venues()` scrapes venues concurrently and reports a `VenueResult` per venue
- **ui/**: `calendar.py` (views + canonical event numbering), `terminal.py` (Rich tables)
- **tests/**: offline parser/date/DB tests (`test_scrapers.py`), pin/star tests, CSV snapshot round-trips

### Data location
Everything lives in `~/.musiclist` (`MUSICLIST_HOME` overrides): `musiclist.db` and `cache/`. On first run, stars and future pins are imported from a legacy `./musiclist.db` in the working directory.

### Refresh semantics
- A venue is re-scraped when its `last_scraped` is older than 24h (or `--force-refresh`).
- A successful scrape upserts events and prunes that venue's *future, unpinned* events that disappeared from the listing (cancelled or renamed shows).
- A fetch failure or an empty parse keeps the existing rows and is flagged in the venue summary ("Fetch failed" / "Nothing parsed").
- Pins and stars always survive refreshes.

### Event numbering
`ui.calendar.numbered_calendar_events()` is the single numbered list behind `music pin <n>`: all configured venues, this month + next, in display order (reverse chronological, so the next show sits right above the prompt). Every view shows these same numbers.

## CLI Commands
```bash
music                    # Calendar view (this month + next)
music calendar --force-refresh
music kilowatt           # Venue view (same as: music venue kilowatt)
music scrape             # All upcoming events, force fetched
music doctor [venue]     # Live scrape, nothing saved; table of counts, time%/price% coverage; exit 1 on failure
music pin 5 | pin "Artist" | unpin 3 | pinned
music star warfield | unstar warfield | starred
music --list-venues
```

## Database Schema
```sql
venues: id, name, base_url, calendar_path, starred, last_scraped
events: id, venue_id, date, time, artists, url, cost, pinned, created_at
UNIQUE: (venue_id, date, artists, url)
```

## Scrapers

### Shared platform scrapers (most venues)
| Scraper | Platform | Notes |
| --- | --- | --- |
| `TicketWebScraper` | TicketWeb WP plugin (`div.tw-section`) | follows `a.next.page-numbers`; yearless dates resolved in listing order |
| `SeeTicketsScraper` | SeeTickets WP plugin | month grids are the full source; list cards add price/support; skips private and cancelled |
| `JsonLdScraper` | schema.org Event JSON-LD | skips parking/upgrades/cancelled; `location_filter` attribute available |
| `DiceScraper` | DICE event-list widget | reads the widget config embedded in the venue page, then pages the same partner API the widget calls |
| `RockhouseScraper` | Rockhouse Partners WP plugin | |

Venue-specific: Café du Nord / Swedish American Hall (one page, `data-room`), Another Planet (`bill_graham.py`), 1015 Folsom, DNA Lounge (monthly calendar pages), Public Works, Warfield, Regency, Bottom of the Hill, Audio, Gray Area.

### BaseScraper helpers
- `scrape()` raises `ScrapeError` on fetch failure; `get_events()` swallows it and returns `[]`
- `_get()` walks `HEADER_PROFILES` for `FETCH_ROUNDS` rounds with backoff (Cloudflare scores some UAs as bots, intermittently)
- `fetch_page()` / `fetch_json()` go through the page cache unless `force_refresh`
- `make_event()` drops incomplete listings and dedupes artists
- Dates: `parse_month_day()` (no year), `parse_date_text()`, `parse_iso_datetime()` (converts to America/Los_Angeles; midnight = no time)
- **Yearless dates**: use `assign_years_in_order()` for any listing in date order. The first entry is anchored at most 90 days back; later entries only move forward (a step back of more than 45 days is a year wrap). `infer_year()` (7-day grace) is only for isolated dates.
- Text: `split_lineup()` (keeps "Simon & Garfunkel" and "AC/DC" intact), `parse_time_ampm()`, `extract_price_from_text()`

## Adding New Venues
1. Check the venue's calendar page source for a known platform: `tw-section` (TicketWeb), `seetickets-calendar` (SeeTickets), `application/ld+json` with Events, `DiceEventListWidget`, `rhpSingleEvent` (Rockhouse).
2. If it matches, add a `VENUES_CONFIG` entry pointing at the shared scraper. Done.
3. Otherwise write a scraper with `parse_events(html) -> List[Event]` using the base helpers, and add a fixture test in `tests/test_scrapers.py`.
4. Run `music doctor <venue>`: shows, last date, and time/price coverage should look right.

## Testing
```bash
make test                       # everything, offline
python -m unittest tests.test_scrapers
music doctor                    # live: catches site drift the offline tests can't
```

## Dependencies
requests, beautifulsoup4, lxml, rich, python-dateutil (pyproject.toml). Python ≥ 3.9.
