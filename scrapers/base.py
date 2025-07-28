import re
import requests
import time
from abc import ABC, abstractmethod
from datetime import time as dt_time, date
from typing import List, Optional
from urllib.parse import urljoin

from models import Event, Venue
from storage import Cache


class BaseScraper(ABC):
    def __init__(self, venue: Venue, cache: Optional[Cache] = None):
        self.venue = venue
        self.cache = cache or Cache()

        # Common headers to avoid being blocked
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }

    def find_calendar_url(self) -> str:
        """Locate venue's calendar/events page"""
        return self.venue.calendar_url

    def fetch_page(self, url: Optional[str] = None) -> str:
        """Fetch page content with caching"""
        target_url = url or self.find_calendar_url()

        # Try cache first
        cached_content = self.cache.get(self.venue.name, target_url)
        if cached_content:
            return cached_content

        # Fetch from web with retry logic
        for attempt in range(3):
            try:
                response = requests.get(target_url, headers=self.headers, timeout=5)
                response.raise_for_status()

                content = response.text
                self.cache.set(self.venue.name, target_url, content)
                return content

            except requests.RequestException as e:
                if attempt == 2:  # Last attempt
                    raise Exception(f"Failed to fetch {target_url}: {e}")
                time.sleep(2**attempt)  # Exponential backoff

    @abstractmethod
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from HTML content (venue-specific)"""
        pass

    def get_events(self) -> List[Event]:
        """Main public interface to get all events"""
        try:
            html_content = self.fetch_page()
            events = self.parse_events(html_content)
            return [event for event in events if event]  # Filter out None values
        except Exception as e:
            print(f"Error scraping {self.venue.name}: {e}")
            return []

    # Common utility methods for reuse by venue scrapers

    def parse_time_ampm(self, time_text: str) -> Optional[dt_time]:
        """Parse time in AM/PM format (e.g., '8:00 pm', '11:30AM')"""
        time_pattern = r"(\d{1,2}):?(\d{2})?\s*(pm|am)"
        match = re.search(time_pattern, time_text, re.IGNORECASE)

        if match:
            try:
                hour = int(match.group(1))
                minute = int(match.group(2) or 0)
                am_pm = match.group(3).lower()

                if am_pm == "pm" and hour != 12:
                    hour += 12
                elif am_pm == "am" and hour == 12:
                    hour = 0

                return dt_time(hour, minute)
            except ValueError:
                pass

        return None

    def month_name_to_number(self, month_name: str) -> Optional[int]:
        """Convert month name to number (handles full names and abbreviations)"""
        months = {
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
        return months.get(month_name.lower())

    def clean_artist_names(self, artist_text: str) -> List[str]:
        """Clean and split artist names, removing common venue additions"""
        if not artist_text:
            return []

        # Remove common venue-added text
        artist_text = re.sub(
            r'["""].*?["""]', "", artist_text
        )  # Remove quoted text like "THE PREVAIL TOUR"
        artist_text = re.sub(
            r"—.*$", "", artist_text
        )  # Remove everything after em dash like "—XOXO Tour"
        artist_text = re.sub(
            r"-.*tour.*$", "", artist_text, re.IGNORECASE
        )  # Remove tour info
        artist_text = artist_text.strip()

        if not artist_text:
            return []

        # Split on common separators
        for separator in [",", "&", " AND ", " WITH ", ", "]:
            if separator in artist_text:
                parts = [part.strip() for part in artist_text.split(separator)]
                return [p.upper() for p in parts if p.strip()]

        return [artist_text.upper()]

    def clean_text(self, text: str) -> str:
        """Generic text cleaning utility"""
        if not text:
            return ""

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def extract_price_from_text(self, text: str) -> Optional[str]:
        """Extract price information from text (e.g., '$25', 'Free', '$15-$25')"""
        if not text:
            return None

        # Look for common price patterns
        price_patterns = [
            r"\$\d+(?:\.\d{2})?(?:\s*-\s*\$\d+(?:\.\d{2})?)?",  # $25, $25.00, $15-$25
            r"free",  # Free
            r"no cover",  # No cover
            r"donation",  # Donation
            r"tbd",  # TBD
        ]

        for pattern in price_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()

        return None

    def parse_full_date_format(self, date_text: str) -> Optional[date]:
        """Parse full date format like 'Wed, Jul 23, 2025' or 'Wednesday, July 23, 2025'"""
        if not date_text:
            return None

        try:
            # Clean up the date text (remove extra whitespace)
            date_text = re.sub(r"\s+", " ", date_text.strip())

            # Try common full date patterns
            patterns = [
                r"(\w+),\s*(\w+)\s+(\d{1,2}),\s*(\d{4})",  # "Wed, Jul 23, 2025"
                r"(\w+)\s+(\w+)\s+(\d{1,2}),?\s*(\d{4})",  # "Wednesday July 23, 2025" or "Wednesday July 23 2025"
            ]

            for pattern in patterns:
                match = re.search(pattern, date_text)
                if match:
                    day_name, month_name, day, year = match.groups()

                    # Convert month name to number
                    month_num = self.month_name_to_number(month_name)
                    if month_num:
                        return date(int(year), month_num, int(day))

        except (ValueError, AttributeError):
            pass

        return None

    # Common event parsing methods for venue scrapers

    def parse_single_event(self, element) -> Optional[Event]:
        """Parse a single event from HTML element (common flow for all venues)"""
        try:
            # Extract date
            event_date = self._extract_date(element)
            if not event_date:
                return None

            # Extract time
            event_time = self._extract_time(element)

            # Extract artists
            artists = self._extract_artists(element)
            if not artists:
                return None

            # Extract URL
            event_url = self._extract_url(element)
            if not event_url:
                return None

            # Extract cost
            event_cost = self._extract_cost(element)

            return Event(
                date=event_date,
                time=event_time,
                artists=artists,
                venue=self.venue.name,
                url=event_url,
                cost=event_cost,
            )

        except Exception as e:
            print(f"Error parsing event: {e}")
            return None

    def extract_cost_generic(self, element) -> Optional[str]:
        """Generic cost extraction method that works for most venues"""
        # Look for price information in various locations
        price_elements = element.find_all(
            ["span", "div"], string=lambda text: text and "$" in text
        )

        for price_elem in price_elements:
            price_text = price_elem.get_text().strip()
            cost = self.extract_price_from_text(price_text)
            if cost:
                return cost

        # If no price found, check if it's free
        text_content = element.get_text().lower()
        if "free" in text_content:
            return "Free"

        # Default to None if no price information found
        return None

    # Abstract methods that each venue scraper must implement

    @abstractmethod
    def _extract_date(self, element) -> Optional[date]:
        """Extract date from venue-specific event element"""
        pass

    @abstractmethod
    def _extract_time(self, element) -> Optional[dt_time]:
        """Extract time from venue-specific event element"""
        pass

    @abstractmethod
    def _extract_artists(self, element) -> List[str]:
        """Extract artist names from venue-specific event element"""
        pass

    @abstractmethod
    def _extract_url(self, element) -> Optional[str]:
        """Extract event URL from venue-specific event element"""
        pass

    def _extract_cost(self, element) -> Optional[str]:
        """Default cost extraction - can be overridden by venue scrapers"""
        return self.extract_cost_generic(element)
