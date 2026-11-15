import json
import re
import time
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta, time as dt_time
from typing import Iterable, List, Optional

import requests

from models import Event, Venue
from storage import Cache


class ScrapeError(Exception):
    """Raised when a venue page cannot be fetched."""


# Venue sites sit behind a mix of CDNs and bot filters. Cloudflare in
# particular scores requests and may reject one header set while accepting
# another, so fetches walk this list until one succeeds.
HEADER_PROFILES = [
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    },
]

REQUEST_TIMEOUT = 15
FETCH_ROUNDS = 3  # passes over HEADER_PROFILES before giving up

# A listing that shows "11.14" on Nov 15 means yesterday, not next year.
# Only roll a yearless date forward once it is this far in the past.
YEAR_ROLLOVER_GRACE = timedelta(days=7)
# First entry of an ordered listing may be this far in the past (running series)
ANCHOR_LOOKBACK = timedelta(days=90)
# Within an ordered listing, a step back larger than this is a year wrap
ORDER_BACKSTEP = timedelta(days=45)

MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}
_MONTH_RE = (
    r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)


class BaseScraper(ABC):
    def __init__(
        self, venue: Venue, cache: Optional[Cache] = None, force_refresh: bool = False
    ):
        self.venue = venue
        self.cache = cache or Cache()
        self.force_refresh = force_refresh
        self.headers = dict(HEADER_PROFILES[0])

    # ------------------------------------------------------------------ fetch

    def find_calendar_url(self) -> str:
        """Locate venue's calendar/events page"""
        return self.venue.calendar_url

    def _get(
        self, url: str, params=None, headers: Optional[dict] = None
    ) -> requests.Response:
        """GET with header-profile fallback and a short backoff between rounds."""
        last_error = None
        profiles = [headers] if headers else HEADER_PROFILES
        for attempt in range(FETCH_ROUNDS):
            if attempt:
                # Cloudflare's bot scoring is bursty; back off 1s, then 3s
                time.sleep(2 * attempt - 1)
            for profile in profiles:
                try:
                    response = requests.get(
                        url, params=params, headers=profile, timeout=REQUEST_TIMEOUT
                    )
                    if response.status_code in (403, 429, 503):
                        last_error = f"HTTP {response.status_code}"
                        continue
                    response.raise_for_status()
                    return response
                except requests.RequestException as e:
                    last_error = str(e)
        raise ScrapeError(f"Failed to fetch {url}: {last_error}")

    def fetch_page(self, url: Optional[str] = None) -> str:
        """Fetch page content, using the HTTP cache unless a refresh was forced."""
        target_url = url or self.find_calendar_url()

        if not self.force_refresh:
            cached_content = self.cache.get(self.venue.name, target_url)
            if cached_content:
                return cached_content

        content = self._get(target_url).text
        self.cache.set(self.venue.name, target_url, content)
        return content

    def fetch_json(self, url: str, params=None, headers: Optional[dict] = None):
        """Fetch a JSON API response (cached like pages, keyed on the full URL)."""
        request = requests.Request("GET", url, params=params).prepare()
        cache_key = request.url
        if not self.force_refresh:
            cached = self.cache.get(self.venue.name, cache_key)
            if cached:
                return json.loads(cached)
        merged = dict(HEADER_PROFILES[0])
        merged.update(headers or {})
        response = self._get(url, params=params, headers=merged)
        self.cache.set(self.venue.name, cache_key, response.text)
        return response.json()

    # ------------------------------------------------------------------ main

    @abstractmethod
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from HTML content (venue-specific)"""

    def scrape(self) -> List[Event]:
        """Fetch and parse; raises ScrapeError when the venue can't be reached."""
        html_content = self.fetch_page()
        return self.dedupe_events(
            event for event in self.parse_events(html_content) if event
        )

    def get_events(self) -> List[Event]:
        """Fetch and parse, returning [] on failure (kept for callers that don't care why)."""
        try:
            return self.scrape()
        except Exception as e:
            print(f"Error scraping {self.venue.name}: {e}")
            return []

    @staticmethod
    def dedupe_events(events: Iterable[Event]) -> List[Event]:
        """Drop repeated listings (many pages render the same show in several widgets)."""
        seen = set()
        unique = []
        for event in events:
            key = (event.date, event.url, event.artists_display.lower())
            if key in seen:
                continue
            seen.add(key)
            unique.append(event)
        return unique

    def make_event(
        self, event_date, event_time, artists, url, cost=None
    ) -> Optional[Event]:
        """Build an Event, returning None for incomplete listings."""
        if not event_date or not url:
            return None
        if isinstance(artists, str):
            artists = [artists]
        artists = self.dedupe_artists(a for a in (artists or []) if a)
        if not artists:
            return None
        try:
            return Event(
                date=event_date,
                time=event_time,
                artists=artists,
                venue=self.venue.name,
                url=url,
                cost=cost or None,
            )
        except ValueError:
            return None

    # ------------------------------------------------------------------ dates

    @staticmethod
    def infer_year(
        month: int, day: int, today: Optional[date] = None
    ) -> Optional[date]:
        """Resolve a yearless month/day to the nearest sensible upcoming date."""
        today = today or date.today()
        try:
            candidate = date(today.year, month, day)
        except ValueError:
            # Feb 29 in a non-leap year: try next year
            try:
                return date(today.year + 1, month, day)
            except ValueError:
                return None
        if candidate < today - YEAR_ROLLOVER_GRACE:
            try:
                candidate = date(today.year + 1, month, day)
            except ValueError:
                return None
        return candidate

    @staticmethod
    def anchor_date(
        month: int, day: int, today: Optional[date] = None
    ) -> Optional[date]:
        """Earliest occurrence of month/day that is at most ANCHOR_LOOKBACK in the past.

        Used for the first entry of an upcoming-events listing, which may be
        a running series that started a few weeks ago but is never months old.
        """
        today = today or date.today()
        for year in (today.year - 1, today.year, today.year + 1):
            try:
                candidate = date(year, month, day)
            except ValueError:
                continue
            if candidate >= today - ANCHOR_LOOKBACK:
                return candidate
        return None

    def assign_years_in_order(
        self, month_days, previous: Optional[date] = None, today: Optional[date] = None
    ) -> List[Optional[date]]:
        """Resolve yearless dates from a chronologically ordered listing.

        A single cutoff can't work: one venue lists "11.01" meaning a
        recurring night two weeks ago, another lists "10.20" meaning next
        October. Listing order settles it: the first date is anchored near
        today, and the year then only moves forward when the sequence wraps
        (Dec -> Jan). Entries are (month, day, year_or_None).
        """
        resolved = []
        prev = previous
        for month, day, year in month_days:
            if year:
                try:
                    current = date(int(year), month, day)
                except ValueError:
                    current = None
            elif prev is None:
                current = self.anchor_date(month, day, today)
            else:
                current = None
                for y in (prev.year, prev.year + 1):
                    try:
                        candidate = date(y, month, day)
                    except ValueError:
                        continue
                    # Small backwards steps happen (two lists interleaved); a big one is a year wrap
                    if candidate >= prev - ORDER_BACKSTEP:
                        current = candidate
                        break
            resolved.append(current)
            if current:
                prev = current
        return resolved

    def parse_month_day(self, text: str):
        """(month, day, year_or_None) from date text, without inferring a year."""
        if not text:
            return None
        text = re.sub(r"\s+", " ", text.strip())
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
        if m:
            return int(m.group(2)), int(m.group(3)), int(m.group(1))
        m = re.search(
            _MONTH_RE + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s*(\d{4}))?",
            text,
            re.I,
        )
        if m:
            return (
                MONTHS[m.group(1).lower()[:3]],
                int(m.group(2)),
                int(m.group(3)) if m.group(3) else None,
            )
        m = re.search(
            r"\b(\d{1,2})\s+" + _MONTH_RE + r"\.?(?:,?\s*(\d{4}))?", text, re.I
        )
        if m:
            return (
                MONTHS[m.group(2).lower()[:3]],
                int(m.group(1)),
                int(m.group(3)) if m.group(3) else None,
            )
        m = re.search(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b", text)
        if m:
            year = m.group(3)
            if year and len(year) == 2:
                year = "20" + year
            month, day = int(m.group(1)), int(m.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                return month, day, int(year) if year else None
        return None

    def parse_date_text(
        self, text: str, today: Optional[date] = None
    ) -> Optional[date]:
        """Parse the date formats venue sites use.

        Handles ISO ("2026-11-15"), numeric ("11.15", "11/15", "11/15/26"),
        and named-month forms with or without weekday and year
        ("Sun, Nov 15", "Tuesday, November 17, 2026", "15 Nov 2026").
        """
        parts = self.parse_month_day(text)
        return self._resolve(*parts, today) if parts else None

    def _resolve(
        self, month: int, day: int, year: Optional[str], today: Optional[date]
    ) -> Optional[date]:
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None
        if year:
            try:
                return date(int(year), month, day)
            except ValueError:
                return None
        return self.infer_year(month, day, today)

    @staticmethod
    def parse_iso_datetime(value: str):
        """Return (date, time) from an ISO-8601 string; time is None for date-only or midnight placeholders."""
        if not value:
            return None, None
        value = value.strip()
        try:
            if len(value) == 10:
                return date.fromisoformat(value), None
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None, None
        if dt.tzinfo is not None:
            try:
                from zoneinfo import ZoneInfo

                dt = dt.astimezone(ZoneInfo("America/Los_Angeles"))
            except Exception:
                pass
        event_time = dt.time().replace(tzinfo=None, microsecond=0)
        # Ticketing sites use 00:00 / 00:00:01 to mean "no time announced"
        if event_time <= dt_time(0, 0, 1):
            event_time = None
        return dt.date(), event_time

    # ------------------------------------------------------------------ text helpers

    def parse_time_ampm(self, time_text: str) -> Optional[dt_time]:
        """Parse time in AM/PM format (e.g., '8:00 pm', '11:30AM', '8pm')"""
        if not time_text:
            return None
        match = re.search(
            r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?", time_text, re.IGNORECASE
        )
        if match:
            try:
                hour = int(match.group(1))
                minute = int(match.group(2) or 0)
                am_pm = match.group(3).lower()
                if am_pm == "p" and hour != 12:
                    hour += 12
                elif am_pm == "a" and hour == 12:
                    hour = 0
                return dt_time(hour, minute)
            except ValueError:
                pass
        return None

    def month_name_to_number(self, month_name: str) -> Optional[int]:
        """Convert month name to number (handles full names and abbreviations)"""
        if not month_name:
            return None
        return MONTHS.get(month_name.strip().rstrip(".").lower())

    @staticmethod
    def dedupe_artists(artists: Iterable[str]) -> List[str]:
        seen = set()
        result = []
        for artist in artists:
            artist = re.sub(r"\s+", " ", artist).strip(" ,;/|-")
            if artist and artist.lower() not in seen:
                seen.add(artist.lower())
                result.append(artist)
        return result

    def clean_artist_names(self, artist_text: str) -> List[str]:
        """Clean and split artist names, removing common venue additions"""
        if not artist_text:
            return []

        # Remove quoted tour names like "THE PREVAIL TOUR" (straight or curly quotes)
        artist_text = re.sub(r"[\"“”].*?[\"“”]", "", artist_text)
        # Remove everything after an em dash, e.g. "—XOXO Tour"
        artist_text = re.sub(r"\s*[—–]\s.*$", "", artist_text)
        # Remove trailing " - ... Tour" segments
        artist_text = re.sub(
            r"\s+-\s+[^-]*\btour\b.*$", "", artist_text, flags=re.IGNORECASE
        )
        artist_text = artist_text.strip()

        if not artist_text:
            return []

        for separator in [", ", ",", " & ", " AND ", " WITH ", " w/ "]:
            if separator in artist_text:
                parts = [part.strip() for part in artist_text.split(separator)]
                return self.dedupe_artists(p.upper() for p in parts if p.strip())

        return [artist_text.upper()]

    def split_lineup(self, text: str) -> List[str]:
        """Split a free-text lineup on unambiguous separators (keeps 'Simon & Garfunkel' intact)."""
        if not text:
            return []
        text = re.sub(
            r"^\s*(with|w/|plus|feat\.?|featuring)\s+", "", text.strip(), flags=re.I
        )
        parts = re.split(
            r"\s*,\s*|\s+\+\s+|\s+w/\s+|\s+/\s*|\s*/\s+|\s*\|\s*|\s+with\s+|\s+and\s+(?=[A-Z])",
            text,
        )
        return self.dedupe_artists(parts)

    def clean_text(self, text: str) -> str:
        """Generic text cleaning utility"""
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    def extract_price_from_text(self, text: str) -> Optional[str]:
        """Extract price information from text (e.g., '$25', 'Free', '$15-$25')"""
        if not text:
            return None

        price_patterns = [
            r"\$\d+(?:\.\d{2})?(?:\s*[-–]\s*\$?\d+(?:\.\d{2})?)?",  # $25, $25.00, $15-$25
            r"\bfree\b",
            r"no cover",
            r"donation",
        ]

        for pattern in price_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(0).strip()
                return "Free" if value.lower() in ("free", "no cover") else value

        return None

    def parse_full_date_format(self, date_text: str) -> Optional[date]:
        """Parse full date format like 'Wed, Jul 23, 2025' or 'Wednesday, July 23, 2025'"""
        return self.parse_date_text(date_text)

    # ------------------------------------------------------------------ element-based flow

    def parse_single_event(self, element) -> Optional[Event]:
        """Parse a single event from an HTML element via the _extract_* hooks."""
        try:
            return self.make_event(
                self._extract_date(element),
                self._extract_time(element),
                self._extract_artists(element),
                self._extract_url(element),
                self._extract_cost(element),
            )
        except Exception:
            return None

    def extract_cost_generic(self, element) -> Optional[str]:
        """Generic cost extraction method that works for most venues"""
        price_elements = element.find_all(
            ["span", "div", "p"], string=lambda text: text and "$" in text
        )

        for price_elem in price_elements:
            cost = self.extract_price_from_text(price_elem.get_text().strip())
            if cost:
                return cost

        text_content = element.get_text().lower()
        if re.search(r"\bfree\b", text_content):
            return "Free"

        return None

    # Hooks for element-based scrapers. Platform scrapers that parse JSON
    # or whole pages override parse_events instead and can ignore these.

    def _extract_date(self, element) -> Optional[date]:
        return None

    def _extract_time(self, element) -> Optional[dt_time]:
        return None

    def _extract_artists(self, element) -> List[str]:
        return []

    def _extract_url(self, element) -> Optional[str]:
        return None

    def _extract_cost(self, element) -> Optional[str]:
        return self.extract_cost_generic(element)
