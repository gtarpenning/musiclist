from datetime import datetime, date
from typing import List, Optional
from bs4 import BeautifulSoup
import re

from models import Event
from .base import BaseScraper


class RickshawStopScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from Rickshaw Stop's SeeTickets-powered website"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # Find all event containers from SeeTickets system
        event_containers = soup.find_all(
            "div", class_="seetickets-list-event-container"
        )

        for container in event_containers:
            try:
                event = self._parse_single_event(container)
                if event:
                    events.append(event)
            except Exception as e:
                print(f"Error parsing event container: {e}")
                continue

        return events

    def _parse_single_event(self, container) -> Optional[Event]:
        """Parse a single event from a SeeTickets event container"""
        return self.parse_single_event(container)

    def _extract_date(self, element) -> Optional[date]:
        """Extract date from Rickshaw Stop event element"""
        # Look for date in element with class 'date'
        date_elem = element.find("p", class_="date")
        if date_elem:
            date_text = date_elem.get_text().strip()

            # Format is like "Sun Jul 20" or "Wed Jul 23"
            # Need to add current year since it's not provided
            current_year = datetime.now().year

            # Parse pattern: "Day Month DD"
            date_pattern = r"(\w+)\s+(\w+)\s+(\d{1,2})"
            match = re.search(date_pattern, date_text)

            if match:
                try:
                    day_name, month_name, day = match.groups()

                    # Convert month name to number
                    month_num = self.month_name_to_number(month_name)
                    if month_num:
                        parsed_date = date(current_year, month_num, int(day))

                        # If the parsed date is in the past, assume it's for next year
                        today = date.today()
                        if parsed_date < today:
                            parsed_date = date(current_year + 1, month_num, int(day))

                        return parsed_date

                except (ValueError, AttributeError):
                    pass

        return None

    def _extract_time(self, element):
        """Extract time from Rickshaw Stop event element"""
        # Look for show time in doortime-showtime section
        doortime_elem = element.find("p", class_="doortime-showtime")
        if doortime_elem:
            # Look for show time span
            showtime_span = doortime_elem.find("span", class_="see-showtime")
            if showtime_span:
                time_text = showtime_span.get_text().strip()
                return self.parse_time_ampm(time_text)

            # Fallback to door time if show time not found
            doortime_span = doortime_elem.find("span", class_="see-doortime")
            if doortime_span:
                time_text = doortime_span.get_text().strip()
                return self.parse_time_ampm(time_text)

        return None

    def _extract_artists(self, element) -> List[str]:
        """Extract artist names from Rickshaw Stop event element"""
        artists = []

        # Get main headliner(s)
        headliners_elem = element.find("p", class_="headliners")
        if headliners_elem:
            headliner_text = headliners_elem.get_text().strip()
            # Remove tour info (e.g., "- Summer Tour 2025")
            headliner_text = re.sub(
                r"\s*-\s*.*tour.*$", "", headliner_text, flags=re.IGNORECASE
            )
            if headliner_text:
                cleaned_artists = self.clean_artist_names(headliner_text)
                artists.extend(cleaned_artists)

        # Get supporting talent
        supporting_elem = element.find("p", class_="supporting-talent")
        if supporting_elem:
            supporting_text = supporting_elem.get_text().strip()
            # Remove "Supporting Talent: " prefix
            supporting_text = re.sub(
                r"^supporting talent:\s*", "", supporting_text, flags=re.IGNORECASE
            )
            if supporting_text:
                cleaned_supporting = self.clean_artist_names(supporting_text)
                artists.extend(cleaned_supporting)

        # Remove duplicates while preserving order
        seen = set()
        unique_artists = []
        for artist in artists:
            if artist and artist not in seen:
                seen.add(artist)
                unique_artists.append(artist)

        return unique_artists

    def _extract_url(self, element) -> Optional[str]:
        """Extract event URL from Rickshaw Stop event element"""
        # Look for the title link which contains the event URL
        title_elem = element.find("p", class_="title")
        if title_elem:
            link = title_elem.find("a", href=True)
            if link:
                return link.get("href")

        # Fallback - look for any SeeTickets URL in the container
        ticket_link = element.find("a", class_="seetickets-buy-btn")
        if ticket_link:
            return ticket_link.get("href")

        return None

    def _extract_cost(self, element) -> Optional[str]:
        """Extract ticket cost from Rickshaw Stop event element"""
        # Look for price span (though it may be hidden by CSS)
        price_span = element.find("span", class_="price")
        if price_span:
            price_text = price_span.get_text().strip()
            if price_text and price_text != "$":
                return price_text

        # Look for age and price info paragraph
        age_price_elems = element.find_all("p", class_="fs-12")
        for elem in age_price_elems:
            text = elem.get_text()
            if "$" in text:
                cost = self.extract_price_from_text(text)
                if cost:
                    return cost

        return None
