from datetime import datetime, date, time as dt_time
from typing import List, Optional
from bs4 import BeautifulSoup
import re

from models import Event
from .base import BaseScraper


class IndependentScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from The Independent's calendar page by extracting JavaScript data"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # Find the script tag containing event data
        scripts = soup.find_all("script")

        for script in scripts:
            if script.string and "all_events" in script.string:
                script_content = script.string.strip()

                # Extract the all_events array from the JavaScript
                # Look for the pattern: all_events = [...]
                match = re.search(
                    r"all_events\s*=\s*(\[.*?\]);", script_content, re.DOTALL
                )
                if match:
                    events_js = match.group(1)
                    # Parse individual JavaScript objects directly using regex
                    events = self._parse_js_events_regex(events_js)
                    return events

        return events

    def _parse_js_events_regex(self, events_js: str) -> List[Event]:
        """Parse JavaScript events using regex instead of JSON conversion"""
        events = []

        # Find all event objects using regex
        # Match opening brace, capture everything until matching closing brace
        event_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        event_matches = re.findall(event_pattern, events_js, re.DOTALL)

        for event_str in event_matches:
            event = self._parse_single_js_event_regex(event_str)
            if event:
                events.append(event)

        return events

    def _parse_single_js_event_regex(self, event_str: str) -> Optional[Event]:
        """Parse a single JavaScript event object using regex"""
        try:
            # Extract ID
            id_match = re.search(r"id:\s*['\"](\d+)['\"]", event_str)
            event_id = id_match.group(1) if id_match else None

            # Extract start date
            start_match = re.search(r"start:\s*['\"]([^'\"]+)['\"]", event_str)
            if not start_match:
                return None

            start_date = start_match.group(1)
            event_date = datetime.strptime(start_date, "%Y-%m-%d").date()

            # Extract title
            title_match = re.search(r"title:\s*['\"]([^'\"]+)['\"]", event_str)
            if not title_match:
                return None

            title = title_match.group(1).strip()
            title = self._clean_html_entities(title)
            artists = [title]

            # Extract time information from doors and displayTime
            event_time = None

            # Try doors first
            doors_match = re.search(r"doors:\s*['\"]([^'\"]*)['\"]", event_str)
            if doors_match:
                doors_text = doors_match.group(1)
                event_time = self._extract_time_from_text(doors_text)

            # If no time from doors, try displayTime
            if not event_time:
                display_match = re.search(
                    r"displayTime:\s*['\"]([^'\"]*)['\"]", event_str
                )
                if display_match:
                    display_text = display_match.group(1)
                    event_time = self._extract_time_from_text(display_text)

            # Create event URL
            event_url = "https://www.theindependentsf.com/calendar/"
            if event_id:
                event_url = f"https://www.theindependentsf.com/calendar/#tw-event-dialog-{event_id}"

            # Create the event
            event = Event(
                date=event_date,
                time=event_time,
                artists=artists,
                venue="The Independent",
                url=event_url,
            )

            return event

        except (ValueError, TypeError) as e:
            return None

    def _clean_html_entities(self, text: str) -> str:
        """Clean HTML entities from text"""
        # Common HTML entities
        replacements = {
            "&amp;": "&",
            "&#8217;": "'",
            "&uacute;": "ú",
            "&auml;": "ä",
            "&#8211;": "–",
            "&nbsp;": " ",
        }

        for entity, replacement in replacements.items():
            text = text.replace(entity, replacement)

        return text

    def _extract_time_from_text(self, time_text: str) -> Optional[dt_time]:
        """Extract time from text like 'Doors: 7:30 PM' or 'Show: 8:00 PM'"""
        # Look for time patterns
        time_patterns = [
            r"(\d{1,2}):(\d{2})\s*(AM|PM)",
            r"(\d{1,2}):(\d{2})\s*(am|pm)",
            r"(\d{1,2}):(\d{2})",
        ]

        for pattern in time_patterns:
            match = re.search(pattern, time_text, re.IGNORECASE)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2))

                # Handle AM/PM
                if len(match.groups()) >= 3 and match.group(3):
                    am_pm = match.group(3).upper()
                    if am_pm == "PM" and hour != 12:
                        hour += 12
                    elif am_pm == "AM" and hour == 12:
                        hour = 0

                try:
                    return dt_time(hour, minute)
                except ValueError:
                    continue

        return None

    def _parse_single_event(self, element) -> Optional[Event]:
        """This method is not used for Independent scraper but required by base class"""
        return None

    def _extract_date(self, element) -> Optional[date]:
        """This method is not used for Independent scraper but required by base class"""
        return None

    def _extract_time(self, element) -> Optional[dt_time]:
        """This method is not used for Independent scraper but required by base class"""
        return None

    def _extract_artists(self, element) -> List[str]:
        """This method is not used for Independent scraper but required by base class"""
        return []

    def _extract_url(self, element) -> Optional[str]:
        """This method is not used for Independent scraper but required by base class"""
        return None
