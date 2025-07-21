from datetime import datetime, date, time as dt_time
from typing import List, Optional
from bs4 import BeautifulSoup
import re

from models import Event
from .base import BaseScraper


class GAMHScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from Great American Music Hall's calendar page"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # Find all calendar tables (one for each month)
        calendar_tables = soup.find_all("table", class_="seetickets-calendar")

        for table in calendar_tables:
            # Get the month and year from the preceding header
            month_header = table.find_previous(
                "div", class_="seetickets-calendar-year-month-container"
            )
            if not month_header:
                continue

            # Extract month and year from header like "October 2025"
            header_text = month_header.get_text().strip()
            month_year_match = re.search(r"(\w+)\s+(\d{4})", header_text)
            if not month_year_match:
                continue

            month_name, year_str = month_year_match.groups()
            year = int(year_str)
            month = self.month_name_to_number(month_name.lower())

            # Process each table row
            for row in table.find_all("tr"):
                cells = row.find_all("td")

                for cell in cells:
                    # Get the date number for this cell
                    date_div = cell.find("div", class_="fs-16 date-number")
                    if not date_div:
                        continue

                    try:
                        day = int(date_div.get_text().strip())
                    except ValueError:
                        continue

                    # Find all event containers in this date cell
                    event_containers = cell.find_all(
                        "div", class_="seetickets-calendar-event-container"
                    )

                    for container in event_containers:
                        # Create a date object for this event
                        try:
                            event_date = date(year, month, day)
                        except ValueError:
                            continue

                        # Create a combined element that includes both the date and the container
                        container._event_date = event_date  # Store date on the element

                        event = self._parse_single_event(container)
                        if event:
                            events.append(event)

        return events

    def _parse_single_event(self, element) -> Optional[Event]:
        """Parse a single event from HTML element"""
        return self.parse_single_event(element)

    def _extract_date(self, element) -> Optional[date]:
        """Extract date from GAMH event element"""
        # The date should have been attached to the element during parsing
        return getattr(element, "_event_date", None)

    def _extract_time(self, element) -> Optional[dt_time]:
        """Extract time from GAMH event element"""
        # Look for showtime in doortime-showtime paragraph
        showtime_p = element.find("p", class_="doortime-showtime")
        if not showtime_p:
            return None

        showtime_text = showtime_p.get_text().strip()

        # Extract time from text like "Event Showtime: 8:00PM"
        time_match = re.search(
            r"Event Showtime:\s*(\d{1,2}:\d{2}(?:AM|PM))", showtime_text, re.IGNORECASE
        )
        if not time_match:
            return None

        time_str = time_match.group(1).strip()
        return self.parse_time_ampm(time_str)

    def _extract_artists(self, element) -> List[str]:
        """Extract artist names from GAMH event element"""
        artist_parts = []

        # Main artist from event title
        title_link = element.find("p", class_="fs-12 bold m-0")
        if title_link:
            link = title_link.find("a")
            if link:
                main_artist = link.get_text().strip()
                if main_artist and main_artist.upper() != "PRIVATE EVENT":
                    artist_parts.append(main_artist)

        # Supporting acts
        support_p = element.find("p", class_="supporting-talent")
        if support_p:
            support_text = support_p.get_text().strip()
            # Remove "with" prefix
            support_text = re.sub(r"^with\s+", "", support_text, flags=re.IGNORECASE)
            if support_text:
                artist_parts.append(support_text)

        # Combine all artist text and let clean_artist_names handle the parsing
        if artist_parts:
            combined_text = " & ".join(artist_parts)
            return self.clean_artist_names(combined_text)

        return []

    def _extract_url(self, element) -> Optional[str]:
        """Extract event URL from GAMH event element"""
        # Main event URL from the artist title link
        title_link = element.find("p", class_="fs-12 bold m-0")
        if title_link:
            link = title_link.find("a")
            if link and link.get("href"):
                return link.get("href")

        # Fallback to image link
        image_link = element.find("a", class_="seetickets-calendar-event-picture")
        if image_link and image_link.get("href"):
            return image_link.get("href")

        return None
