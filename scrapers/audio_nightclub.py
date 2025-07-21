from datetime import datetime, date
from typing import List, Optional
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

from models import Event
from .base import BaseScraper


class AudioNightclubScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from Audio Nightclub's events page"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # Find all event container blocks
        event_blocks = soup.find_all("div", {"id": "events-container-block"})

        for block in event_blocks:
            event = self._parse_single_event(block)
            if event:
                events.append(event)

        return events

    def _parse_single_event(self, element) -> Optional[Event]:
        """Parse a single event from HTML element"""
        return self.parse_single_event(element)

    def _extract_date(self, element) -> Optional[date]:
        """Extract date from Audio Nightclub event element"""
        # Look for the date span
        date_span = element.find("span", {"class": "event-container-top-date"})
        if not date_span:
            return None

        date_link = date_span.find("a")
        if not date_link:
            return None

        date_text = date_link.get_text().strip()

        # Pattern: "Sun. Jul 20", "Fri. Aug 01", "Thu. Nov 20"
        date_pattern = r"(\w+)\.\s*(\w+)\s+(\d+)"
        match = re.search(date_pattern, date_text)

        if match:
            try:
                day_name, month_name, day = match.groups()
                month_num = self.month_name_to_number(month_name)

                if month_num:
                    # Use current year, but adjust if month has passed
                    current_year = datetime.now().year
                    current_month = datetime.now().month

                    # If event month is before current month, assume next year
                    if month_num < current_month:
                        current_year += 1

                    return date(current_year, month_num, int(day))

            except (ValueError, AttributeError):
                pass

        return None

    def _extract_time(self, element):
        """Extract time from Audio Nightclub event element"""
        # Audio Nightclub doesn't appear to show event times on the main events page
        # The time might be on individual event pages, but for now return None
        return None

    def _extract_artists(self, element) -> List[str]:
        """Extract artist names from Audio Nightclub event element"""
        artists = []

        # Look for the event title
        title_span = element.find("span", {"class": "events-container-block-in-title"})
        if not title_span:
            return artists

        title_link = title_span.find("a")
        if not title_link:
            return artists

        title_text = title_link.get_text().strip()

        if title_text:
            # Clean up the title and extract artist names
            cleaned_artists = self.clean_artist_names(title_text)
            artists.extend(cleaned_artists)

        return artists

    def _extract_url(self, element) -> Optional[str]:
        """Extract event URL from Audio Nightclub event element"""
        # Look for the link in the title
        title_span = element.find("span", {"class": "events-container-block-in-title"})
        if title_span:
            title_link = title_span.find("a", href=True)
            if title_link:
                url = title_link["href"]
                # Make absolute URL
                return urljoin(self.venue.base_url, url)

        # If no specific event URL, return the venue's main page
        return self.venue.base_url

    def _extract_cost(self, element) -> Optional[str]:
        """Extract ticket cost from Audio Nightclub event element"""
        # Cost information doesn't appear to be shown on the main events page
        # Would need to visit individual event pages to get pricing
        return None
