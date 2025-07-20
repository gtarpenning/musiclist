from datetime import datetime, date
from typing import List, Optional
from bs4 import BeautifulSoup

from models import Event
from .base import BaseScraper


class WarfieldScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from The Warfield's events page"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # Look for The Warfield specific event containers
        event_elements = soup.find_all("div", class_="info")

        for element in event_elements:
            # Only process elements that have date-time-container (actual events)
            if element.find("div", class_="date-time-container"):
                event = self._parse_single_event(element)
                if event:
                    events.append(event)

        return events

    def _parse_single_event(self, element) -> Optional[Event]:
        """Parse a single event from HTML element"""
        # Use the shared implementation from base class
        return self.parse_single_event(element)

    def _extract_date(self, element) -> Optional[date]:
        """Extract date from The Warfield event element"""
        # Look for the date span
        date_span = element.find("span", class_="date")
        if not date_span:
            return None

        date_text = date_span.get_text().strip()  # Format like "Wed, Jul 23, 2025"

        # Use base utility for full date format parsing
        return self.parse_full_date_format(date_text)

    def _extract_time(self, element):
        """Extract time from The Warfield event element"""
        # Look for the time span
        time_span = element.find("span", class_="time")
        if not time_span:
            return None

        time_text = time_span.get_text().strip()

        # The text includes "Show" and newlines, extract just the time part
        # Format is like "Show\n                                        8:00 PM\n\n                        "
        lines = [line.strip() for line in time_text.split("\n") if line.strip()]
        for line in lines:
            if "PM" in line or "AM" in line:
                # Use base utility for AM/PM parsing
                return self.parse_time_ampm(line)

        return None

    def _extract_artists(self, element) -> List[str]:
        """Extract artist names from The Warfield event element"""
        artists = []

        # Main artist is in h3 with class carousel_item_title_small
        main_artist_h3 = element.find("h3", class_="carousel_item_title_small")
        if main_artist_h3:
            main_artist_link = main_artist_h3.find("a")
            if main_artist_link:
                main_artist = main_artist_link.get_text().strip()
                if main_artist:
                    artists.append(main_artist.upper())

        # Supporting artists are in h4 with class animated (format: "with [Artist]")
        support_artist_h4 = element.find("h4", class_="animated")
        if support_artist_h4:
            support_text = support_artist_h4.get_text().strip()
            if support_text.lower().startswith("with "):
                support_artist = support_text[5:].strip()  # Remove "with " prefix
                if support_artist:
                    artists.append(support_artist.upper())

        return artists

    def _extract_url(self, element) -> Optional[str]:
        """Extract event URL from The Warfield element"""
        # Main event link is in the h3 -> a tag
        main_artist_h3 = element.find("h3", class_="carousel_item_title_small")
        if main_artist_h3:
            link = main_artist_h3.find("a", href=True)
            if link:
                url = link["href"]
                # The Warfield URLs are already absolute
                return url

        return None

    def _extract_cost(self, element) -> Optional[str]:
        """Extract ticket cost from The Warfield event element"""
        # Use the shared generic cost extraction
        return self.extract_cost_generic(element)
