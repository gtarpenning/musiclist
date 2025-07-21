from datetime import datetime, date
from typing import List, Optional
from bs4 import BeautifulSoup
import re

from models import Event
from .base import BaseScraper


class Bimbos365Scraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from Bimbo's 365 Club shows page"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # Find all event sections
        event_sections = soup.find_all("div", class_="tw-section")

        for section in event_sections:
            event = self._parse_single_event(section)
            if event:
                events.append(event)

        return events

    def _parse_single_event(self, element) -> Optional[Event]:
        """Parse a single event from HTML element"""
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

            # Extract cost - Bimbo's doesn't display cost directly, so we'll leave it None
            cost = None

            return Event(
                date=event_date,
                time=event_time,
                artists=artists,
                venue="Bimbo's 365 Club",
                url=event_url,
                cost=cost,
            )

        except Exception as e:
            return None

    def _extract_date(self, element) -> Optional[date]:
        """Extract date from Bimbo's event element"""
        month_span = element.find("span", class_="tw-event-month")
        date_span = element.find("span", class_="tw-event-date")

        if not month_span or not date_span:
            return None

        month_text = month_span.get_text().strip()
        day_text = date_span.get_text().strip()

        # Convert month name to number
        month_num = self.month_name_to_number(month_text)
        if not month_num:
            return None

        try:
            day = int(day_text)

            # Assume current year if not specified - typical for event sites
            current_year = datetime.now().year

            # If the month/day has already passed this year, assume next year
            current_date = datetime.now().date()
            try_date = date(current_year, month_num, day)

            if try_date < current_date:
                return date(current_year + 1, month_num, day)
            else:
                return try_date

        except ValueError:
            return None

    def _extract_time(self, element) -> Optional[str]:
        """Extract time from Bimbo's event element"""
        # Look for show time first (more reliable than door time)
        show_time_span = element.find("span", class_="tw-event-time")
        if show_time_span:
            time_text = show_time_span.get_text().strip()
            parsed_time = self.parse_time_ampm(time_text)
            if parsed_time:
                return parsed_time

        # Fallback to door time
        door_time_span = element.find("span", class_="tw-event-door-time")
        if door_time_span:
            time_text = door_time_span.get_text().strip()
            parsed_time = self.parse_time_ampm(time_text)
            if parsed_time:
                return parsed_time

        return None

    def _extract_artists(self, element) -> List[str]:
        """Extract artist names from Bimbo's event element"""
        artists = []

        # Main artist is in the tw-name div
        name_div = element.find("div", class_="tw-name")
        if name_div:
            name_link = name_div.find("a")
            if name_link:
                main_artist = name_link.get_text().strip()
                if main_artist:
                    # Clean up HTML entities
                    main_artist = main_artist.replace("&amp;", "&")
                    main_artist = main_artist.replace("&eacute;", "é")
                    artists.append(main_artist.upper())

        # Supporting artists are in tw-attractions div with "with [artist]" format
        attractions_div = element.find("div", class_="tw-attractions")
        if attractions_div:
            attractions_text = attractions_div.get_text().strip()
            if attractions_text.lower().startswith("with "):
                # Extract supporting artist names
                support_text = attractions_text[5:].strip()  # Remove "with " prefix

                # Look for spans inside for multiple artists
                spans = attractions_div.find_all("span")
                if spans:
                    for span in spans:
                        support_artist = span.get_text().strip()
                        if support_artist:
                            support_artist = support_artist.replace("&amp;", "&")
                            artists.append(support_artist.upper())
                elif support_text:
                    # Single support artist
                    support_text = support_text.replace("&amp;", "&")
                    artists.append(support_text.upper())

        return artists

    def _extract_url(self, element) -> Optional[str]:
        """Extract event URL from Bimbo's element"""
        # Event URL is in the tw-name div -> a tag
        name_div = element.find("div", class_="tw-name")
        if name_div:
            link = name_div.find("a", href=True)
            if link:
                url = link["href"]
                # Ensure absolute URL
                if url.startswith("/"):
                    return f"https://bimbos365club.com{url}"
                elif not url.startswith("http"):
                    return f"https://bimbos365club.com/{url}"
                return url

        return None

    def _extract_cost(self, element) -> Optional[str]:
        """Extract cost from Bimbo's event element - not displayed on main page"""
        # Bimbo's doesn't show ticket prices on the main shows page
        return None
