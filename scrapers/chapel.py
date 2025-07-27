from datetime import datetime, date, time as dt_time
from typing import List, Optional
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

from models import Event
from .base import BaseScraper


class ChapelScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from The Chapel's calendar page"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # The Chapel uses div elements with class "event-info-block" for events
        event_containers = soup.find_all("div", class_="event-info-block")

        # Process each event container
        for container in event_containers:
            if not container or not container.get_text(strip=True):
                continue

            event = self.parse_single_event(container)
            if event:
                events.append(event)

        return events

    def _extract_date(self, element) -> Optional[date]:
        """Extract date from Chapel event element"""
        current_year = datetime.now().year
        element_text = element.get_text()

        # Look for patterns like "Sun Jul 27", "Wed Jul 30" in the event-info-block
        date_patterns = [
            r"(\w{3})\s+(\w{3})\s+(\d{1,2})",  # "Sun Jul 27"
            r"(\w+day)\s+(\w+)\s+(\d{1,2})",  # "Sunday July 27"
        ]

        for pattern in date_patterns:
            match = re.search(pattern, element_text)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    day_name, month_name, day = groups
                    month_num = self.month_name_to_number(month_name)
                    if month_num:
                        try:
                            # For dates in the past, assume next year
                            event_date = date(current_year, month_num, int(day))
                            if event_date < date.today():
                                event_date = date(current_year + 1, month_num, int(day))
                            return event_date
                        except ValueError:
                            try:
                                return date(current_year + 1, month_num, int(day))
                            except ValueError:
                                continue

        return None

    def _extract_time(self, element) -> Optional[dt_time]:
        """Extract time from Chapel event element"""
        element_text = element.get_text()

        # Look for show time patterns
        # Chapel typically shows "Show at 8:00PM" or "Doors at 7:00PM"
        time_patterns = [
            r"Show at (\d{1,2}:\d{2}(?:AM|PM))",
            r"Doors at (\d{1,2}:\d{2}(?:AM|PM))",
            r"(\d{1,2}:\d{2}(?:AM|PM))",
        ]

        for pattern in time_patterns:
            match = re.search(pattern, element_text, re.IGNORECASE)
            if match:
                time_str = match.group(1)
                parsed_time = self.parse_time_ampm(time_str)
                if parsed_time:
                    return parsed_time

        return None

    def _extract_artists(self, element) -> List[str]:
        """Extract artist names from Chapel event element"""
        # Look for the main event title - it's in a <p> tag with class "title"
        title_elem = element.find("p", class_="title")
        if title_elem:
            title_link = title_elem.find("a")
            if title_link:
                main_artist = title_link.get_text(strip=True)
                if main_artist:
                    return [main_artist.upper()]

        # Fallback: extract from element text
        element_text = element.get_text()

        # Extract the lineup after the date pattern
        # Format: "LOVE SUPREME Summer Day Party SeriesSun Jul 27DINA, SAZON LIBRE, ..."
        date_match = re.search(r"(\w{3})\s+(\w{3})\s+(\d{1,2})", element_text)
        if date_match:
            # Get text after the date
            after_date = element_text[date_match.end() :].strip()

            # Look for the artist lineup before "Doors at" or "Show at"
            lineup_match = re.search(r"^([^D]*?)(?=Doors at|Show at)", after_date)
            if lineup_match:
                lineup_text = lineup_match.group(1).strip()
                if lineup_text:
                    # Clean up the lineup text and return just the first main part
                    artists = self.clean_artist_names(lineup_text)
                    return artists[:3] if artists else []  # Limit to first 3 artists

        return []

    def _extract_url(self, element) -> Optional[str]:
        """Extract event URL from Chapel event element"""
        # Look for ticket purchase links or event detail links
        link_selectors = [
            "a[href*='seetickets']",  # SeeTickets links
            "a[href*='event']",  # Event detail links
            "a[href*='ticket']",  # General ticket links
            "a",  # Any link as fallback
        ]

        for selector in link_selectors:
            links = element.select(selector)
            for link in links:
                href = link.get("href")
                if href:
                    # Convert relative URLs to absolute
                    if href.startswith("/"):
                        href = urljoin("https://thechapelsf.com", href)
                    elif not href.startswith("http"):
                        href = urljoin("https://thechapelsf.com/", href)
                    return href

        return None

    def _extract_cost(self, element) -> Optional[str]:
        """Extract cost information from Chapel event element"""
        element_text = element.get_text()

        # Look for price patterns
        price_patterns = [
            r"All Ages,\s*(\$[\d\.]+-?\$?[\d\.]*)",  # "All Ages, $22.00-$25.00"
            r"21\+,\s*(\$[\d\.]+-?\$?[\d\.]*)",  # "21+, $15.00"
            r"18\+,\s*(\$[\d\.]+-?\$?[\d\.]*)",  # "18+, $30.00-$600.00"
            r"(\$\d+(?:\.\d{2})?(?:\s*-\s*\$\d+(?:\.\d{2})?)?)",  # General $price patterns
            r"(Free|FREE)",  # Free events
        ]

        for pattern in price_patterns:
            match = re.search(pattern, element_text)
            if match:
                return match.group(1).strip()

        return None
