from datetime import datetime, date
from typing import List, Optional
from bs4 import BeautifulSoup
import re

from models import Event
from .base import BaseScraper


class GrayAreaScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from Gray Area's events page"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # Find all event items
        event_items = soup.find_all("div", class_="item")

        for item in event_items:
            event = self.parse_single_event(item)
            if event:
                events.append(event)

        return events

    def _extract_date(self, element) -> Optional[date]:
        """Extract date from Gray Area event element"""
        date_elem = element.find("div", class_="date")
        if not date_elem:
            return None

        date_text = date_elem.get_text().strip()

        # Date format is MM/DD (e.g., "07/31")
        date_pattern = r"(\d{1,2})/(\d{1,2})"
        match = re.search(date_pattern, date_text)

        if match:
            month, day = match.groups()

            # Determine year - if month/day has passed this year, assume next year
            current_date = date.today()
            current_year = current_date.year

            try:
                event_date = date(current_year, int(month), int(day))

                # If the event date has already passed this year, assume it's next year
                if event_date < current_date:
                    event_date = date(current_year + 1, int(month), int(day))

                return event_date

            except ValueError:
                # Invalid date
                pass

        return None

    def _extract_time(self, element) -> Optional[object]:
        """Extract time from Gray Area event element"""
        # Time information is not available in the listing page
        # Would need to fetch individual event pages for time details
        return None

    def _extract_artists(self, element) -> List[str]:
        """Extract artist/event names from Gray Area event element"""
        title_elem = element.find("h5", class_="item-title")
        if not title_elem:
            return []

        # Get the text content, handling HTML tags
        title_text = title_elem.get_text()

        # Clean up common formatting
        title_text = re.sub(r"\s+", " ", title_text)  # Replace multiple spaces
        title_text = title_text.strip()

        # Remove common prefixes that aren't part of the artist name
        title_text = re.sub(r"^(SOLD OUT!\s*)", "", title_text, flags=re.IGNORECASE)
        title_text = re.sub(r"^(Workshop\s*)", "", title_text, flags=re.IGNORECASE)

        if title_text:
            # For Gray Area, the "artist" is really the event name/title
            # Split on common separators but be conservative
            if " with " in title_text.lower():
                # Handle cases like "Event Title with Artist Name"
                parts = re.split(r"\s+with\s+", title_text, flags=re.IGNORECASE)
                return [part.strip().upper() for part in parts if part.strip()]
            elif " + " in title_text:
                # Handle cases like "Artist1 + Artist2"
                parts = title_text.split(" + ")
                return [part.strip().upper() for part in parts if part.strip()]
            else:
                # Single event title
                return [title_text.upper()]

        return []

    def _extract_url(self, element) -> Optional[str]:
        """Extract event URL from Gray Area event element"""
        link_elem = element.find("a", class_="item-link")
        if link_elem and link_elem.get("href"):
            href = link_elem["href"]

            # Ensure absolute URL
            if href.startswith("http"):
                return href
            else:
                return f"https://grayarea.org{href}"

        return None

    def _extract_cost(self, element) -> Optional[str]:
        """Extract cost information from Gray Area event element"""
        # Cost information is typically not shown in the main listing
        # Would need to fetch individual event pages for pricing

        # Check if it's sold out
        title_elem = element.find("h5", class_="item-title")
        if title_elem and "SOLD OUT" in title_elem.get_text().upper():
            return "Sold Out"

        return None
