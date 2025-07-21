from datetime import datetime, date
from typing import List, Optional
from bs4 import BeautifulSoup
import re

from models import Event
from .base import BaseScraper


class PublicWorksScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from Public Works' calendar page"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # Find the eventbrite-items container
        eventbrite_items = soup.find("div", class_="eventbrite-items")
        if not eventbrite_items:
            return events

        # Find all event items
        event_items = eventbrite_items.find_all("div", class_="event-item")

        # Keep track of current month for date parsing
        current_month = None

        # Also find month headers to track the current month
        for element in eventbrite_items.find_all(["div"]):
            if element.get("class") == ["event-month"]:
                month_h3 = element.find("h3")
                if month_h3:
                    current_month = month_h3.get_text().strip()
            elif element.get("class") == ["event-item"]:
                if current_month:
                    event = self._parse_single_event_with_month(element, current_month)
                    if event:
                        events.append(event)

        return events

    def _parse_single_event_with_month(self, element, month: str) -> Optional[Event]:
        """Parse a single event from HTML element with known month"""
        try:
            # Extract date
            event_date = self._extract_date_with_month(element, month)
            if not event_date:
                return None

            # Extract time - Public Works doesn't show time in listing, so we'll leave it None
            event_time = None

            # Extract artists from title
            artists = self._extract_artists(element)
            if not artists:
                return None

            # Extract URL
            event_url = self._extract_url(element)
            if not event_url:
                return None

            # Extract cost - not visible in the listing, so we'll leave it None
            event_cost = None

            return Event(
                date=event_date,
                time=event_time,
                artists=artists,
                venue=self.venue.name,
                url=event_url,
                cost=event_cost,
            )

        except Exception as e:
            print(f"Error parsing Public Works event: {e}")
            return None

    def _extract_date_with_month(self, element, month: str) -> Optional[date]:
        """Extract date from Public Works event element with known month"""
        date_elem = element.find("div", class_="event-date")
        if not date_elem:
            return None

        date_text = date_elem.get_text().strip()

        # Format is "Jul 23", "Aug 01", etc.
        # Split to get just the day number
        parts = date_text.split()
        if len(parts) >= 2:
            try:
                day = int(parts[1])

                # Convert month abbreviation to number
                month_num = self.month_name_to_number(month)
                if not month_num:
                    return None

                # Use current year, but adjust if month has passed
                current_year = datetime.now().year
                current_month = datetime.now().month

                # If event month is before current month, assume next year
                if month_num < current_month:
                    current_year += 1

                return date(current_year, month_num, day)

            except (ValueError, IndexError):
                pass

        return None

    def _extract_date(self, element) -> Optional[date]:
        """Required by base class - not used in this implementation"""
        return None

    def _extract_time(self, element):
        """Extract time - Public Works doesn't show time in listings"""
        return None

    def _extract_artists(self, element) -> List[str]:
        """Extract artist names from Public Works event element"""
        title_elem = element.find("div", class_="event-title")
        if not title_elem:
            return []

        title_text = title_elem.get_text().strip()

        # Clean up common venue additions from titles
        # Remove "presented by..." text
        title_text = re.sub(r"presented by.*$", "", title_text, flags=re.IGNORECASE)

        # Remove tour names and other common additions
        title_text = re.sub(r'["""].*?["""]', "", title_text)  # Remove quoted text
        title_text = re.sub(r"—.*$", "", title_text)  # Remove everything after em dash
        title_text = re.sub(
            r"-.*tour.*$", "", title_text, re.IGNORECASE
        )  # Remove tour info
        title_text = re.sub(r"at Public Works.*$", "", title_text, re.IGNORECASE)
        title_text = re.sub(r"\(.*\)", "", title_text)  # Remove parenthetical content

        title_text = title_text.strip()

        if not title_text:
            return []

        # Clean up artist names using base class method
        return self.clean_artist_names(title_text)

    def _extract_url(self, element) -> Optional[str]:
        """Extract event URL from Public Works element"""
        # The entire event-item is wrapped in an anchor tag
        link = element.find("a", href=True)
        if link:
            return link["href"]

        # If no direct link found, check parent
        parent = element.parent
        if parent and parent.name == "a" and parent.get("href"):
            return parent["href"]

        # Fallback to venue main page
        return self.venue.base_url

    def _extract_cost(self, element) -> Optional[str]:
        """Extract ticket cost - not shown in Public Works listings"""
        return None
