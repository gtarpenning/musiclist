from datetime import datetime, date
from typing import List, Optional
from bs4 import BeautifulSoup

from models import Event
from .base import BaseScraper


class BrickMortarScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from Brick & Mortar's calendar page"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # Look for Brick & Mortar specific event containers
        event_elements = soup.find_all("div", class_="tw-cal-event-popup")

        for element in event_elements:
            event = self._parse_single_event(element)
            if event:
                events.append(event)

        return events

    def _parse_single_event(self, element) -> Optional[Event]:
        """Parse a single event from HTML element"""
        # Use the shared implementation from base class
        return self.parse_single_event(element)

    def _extract_date(self, element) -> Optional[date]:
        """Extract date from Brick & Mortar event element"""
        # Look for the specific tw-event-date span
        date_span = element.find("span", class_="tw-event-date")
        if not date_span:
            return None

        date_text = date_span.get_text().strip()  # Format like "8.20" for August 20

        try:
            # Split on dot and parse month.day format
            if "." in date_text:
                month_str, day_str = date_text.split(".")
                month = int(month_str)
                day = int(day_str)

                # Use current year, but if the month has passed, use next year
                current_year = datetime.now().year
                current_month = datetime.now().month

                # If event month is before current month, assume next year
                if month < current_month:
                    current_year += 1

                return date(current_year, month, day)

        except (ValueError, AttributeError):
            pass

        return None

    def _extract_time(self, element):
        """Extract time from Brick & Mortar event element"""
        # Look for the specific tw-event-time-complete span
        time_span = element.find("span", class_="tw-event-time-complete")
        if not time_span:
            return None

        time_text = time_span.get_text().strip()  # Format like "8:00 pm"

        # Use base utility for AM/PM parsing
        return self.parse_time_ampm(time_text)

    def _extract_artists(self, element) -> List[str]:
        """Extract artist names from Brick & Mortar event element"""
        # Look for the tw-name div with link
        name_div = element.find("div", class_="tw-name")
        if not name_div:
            return []

        name_link = name_div.find("a")
        if not name_link:
            return []

        # Get the artist text and use base utility to clean it
        artist_text = name_link.get_text().strip()
        return self.clean_artist_names(artist_text)

    def _extract_url(self, element) -> Optional[str]:
        """Extract event URL from Brick & Mortar element"""
        # Look for the tw-name div with link
        name_div = element.find("div", class_="tw-name")
        if name_div:
            link = name_div.find("a", href=True)
            if link:
                url = link["href"]
                # Brick & Mortar URLs are already absolute
                return url

        return None

    def _extract_cost(self, element) -> Optional[str]:
        """Extract ticket cost from Brick & Mortar event element"""
        # Use the shared generic cost extraction
        return self.extract_cost_generic(element)
