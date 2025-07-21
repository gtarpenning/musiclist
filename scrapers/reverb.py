from datetime import datetime, date
from typing import List, Optional
from bs4 import BeautifulSoup
import re

from models import Event
from .base import BaseScraper


class ReverbScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from Reverb's website"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # Find the events container section
        events_section = soup.find(
            string=lambda text: text and "UPCOMING EVENTS" in text
        )
        if not events_section:
            return events

        # Find the parent container with the events
        container = events_section.parent
        while container and not container.find_all("div", {"data-ux": "ContentCard"}):
            container = container.parent

        if not container:
            return events

        # Find all event cards
        event_cards = container.find_all("div", {"data-ux": "ContentCard"})

        for card in event_cards:
            try:
                event = self._parse_single_event(card)
                if event:
                    events.append(event)
            except Exception as e:
                print(f"Error parsing event card: {e}")
                continue

        return events

    def _parse_single_event(self, card) -> Optional[Event]:
        """Parse a single event from an event card"""
        return self.parse_single_event(card)

    def _extract_date(self, element) -> Optional[date]:
        """Extract date from Reverb event element"""
        # Look for date in span elements with day and date
        date_spans = element.find_all("span")

        for span in date_spans:
            date_text = span.get_text().strip()

            # Look for patterns like "July 18th, 2025" or "FridayJuly 18th, 2025"
            date_match = re.search(
                r"(\w+day)?(\w+)\s+(\d{1,2})(?:st|nd|rd|th),?\s*(\d{4})", date_text
            )
            if date_match:
                try:
                    month_name = date_match.group(2)
                    day = int(date_match.group(3))
                    year = int(date_match.group(4))

                    month_num = self.month_name_to_number(month_name)
                    if month_num:
                        return date(year, month_num, day)
                except (ValueError, AttributeError):
                    continue

        # Also check text content of the card for date patterns
        all_text = element.get_text()
        date_patterns = [
            r"(\w+day)(\w+)\s+(\d{1,2})(?:st|nd|rd|th),?\s*(\d{4})",  # "FridayJuly 18th, 2025"
            r"(\w+)\s+(\d{1,2})(?:st|nd|rd|th),?\s*(\d{4})",  # "July 18th, 2025"
        ]

        for pattern in date_patterns:
            match = re.search(pattern, all_text)
            if match:
                try:
                    if len(match.groups()) == 4:  # Has day of week
                        month_name = match.group(2)
                        day = int(match.group(3))
                        year = int(match.group(4))
                    else:  # No day of week
                        month_name = match.group(1)
                        day = int(match.group(2))
                        year = int(match.group(3))

                    month_num = self.month_name_to_number(month_name)
                    if month_num:
                        return date(year, month_num, day)
                except (ValueError, AttributeError):
                    continue

        return None

    def _extract_time(self, element):
        """Extract time from Reverb event element"""
        # Most Reverb events don't seem to have specific times listed
        # Return None for now - could be enhanced if times appear
        return None

    def _extract_artists(self, element) -> List[str]:
        """Extract artist names from Reverb event element"""
        artists = []

        # Look for h4 elements which contain the event titles
        title_elements = element.find_all("h4")

        for h4 in title_elements:
            title_text = h4.get_text().strip()

            # Extract artist name from titles like:
            # "Reverb Presents: Adriana Lopez"
            # "Spin & Destroy x Reverb Presents: ADRNLN"
            # "In The Lounge w/ Crash Course"

            if ":" in title_text:
                # Split on colon and take the part after
                artist_part = title_text.split(":", 1)[1].strip()
                if artist_part:
                    cleaned_artists = self.clean_artist_names(artist_part)
                    artists.extend(cleaned_artists)
            elif " w/ " in title_text.lower():
                # Handle "In The Lounge w/ Artist Name" format
                if "w/" in title_text.lower():
                    artist_part = title_text.lower().split("w/")[1].strip()
                    if artist_part:
                        cleaned_artists = self.clean_artist_names(artist_part)
                        artists.extend(cleaned_artists)
            else:
                # If no clear pattern, use the whole title but clean it
                cleaned_artists = self.clean_artist_names(title_text)
                artists.extend(cleaned_artists)

        # Remove duplicates while preserving order
        seen = set()
        unique_artists = []
        for artist in artists:
            if artist and artist not in seen:
                seen.add(artist)
                unique_artists.append(artist)

        return unique_artists

    def _extract_url(self, element) -> Optional[str]:
        """Extract event URL from Reverb event element"""
        # Look for ticket links (Buy Tickets, FREE TICKETS)
        ticket_links = element.find_all("a", href=True)

        for link in ticket_links:
            href = link.get("href", "")
            text = link.get_text().strip().lower()

            # Look for ticket-related links
            if any(word in text for word in ["buy tickets", "free tickets", "tickets"]):
                # Return the ticket URL if it's external
                if href.startswith("http"):
                    return href
                elif href.startswith("/"):
                    return f"{self.venue.base_url.rstrip('/')}{href}"

        # If no ticket links found, return the venue's main page
        return self.venue.base_url

    def _extract_cost(self, element) -> Optional[str]:
        """Extract ticket cost from Reverb event element"""
        # Look for cost information in ticket links
        ticket_links = element.find_all("a", href=True)

        for link in ticket_links:
            text = link.get_text().strip()

            # Check if it's a free event
            if "free" in text.lower():
                return "Free"

            # Look for price patterns in the link text
            cost = self.extract_price_from_text(text)
            if cost:
                return cost

        # Check other text in the element for pricing
        all_text = element.get_text()
        cost = self.extract_price_from_text(all_text)
        if cost:
            return cost

        return None
