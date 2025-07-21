from datetime import datetime, date, time as dt_time
from typing import List, Optional
from bs4 import BeautifulSoup
import re
import json

from models import Event
from .base import BaseScraper


class IndependentScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from The Independent's calendar page by extracting JavaScript data"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # Find the script tag containing event data
        scripts = soup.find_all("script")
        event_data = None

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
                    # Clean up the JavaScript to make it valid JSON
                    events_js = self._clean_js_for_json(events_js)

                    try:
                        event_data = json.loads(events_js)
                        break
                    except json.JSONDecodeError as e:
                        # If JSON parsing fails, try to extract individual events
                        events = self._parse_js_events_fallback(script_content)
                        return events

        if event_data:
            # Parse each event from the extracted data
            for event_info in event_data:
                event = self._parse_js_event(event_info)
                if event:
                    events.append(event)

        return events

    def _clean_js_for_json(self, js_string: str) -> str:
        """Clean JavaScript array to make it valid JSON"""
        # Remove JavaScript comments
        js_string = re.sub(r"//.*?$", "", js_string, flags=re.MULTILINE)

        # Remove trailing commas before closing brackets/braces
        js_string = re.sub(r",(\s*[}\]])", r"\1", js_string)

        # Fix unquoted keys (JavaScript allows unquoted keys, JSON doesn't)
        js_string = re.sub(r"(\w+):", r'"\1":', js_string)

        # Fix single quotes to double quotes
        js_string = re.sub(r"'([^']*)'", r'"\1"', js_string)

        return js_string

    def _parse_js_events_fallback(self, script_content: str) -> List[Event]:
        """Fallback method to parse events using regex if JSON parsing fails"""
        events = []

        # Find individual event objects using regex
        event_pattern = r'\{\s*id:\s*[\'"](\d+)[\'"],.*?start:\s*[\'"]([^\'\"]+)[\'"],.*?title:\s*[\'"]([^\'\"]+)[\'"].*?\}'
        matches = re.findall(event_pattern, script_content, re.DOTALL)

        for match in matches:
            event_id, start_date, title = match
            try:
                # Parse the date
                event_date = datetime.strptime(start_date, "%Y-%m-%d").date()

                # Create event URL with specific event ID
                event_url = f"https://www.theindependentsf.com/calendar/#tw-event-dialog-{event_id}"

                # Create event
                event = Event(
                    date=event_date,
                    time=None,  # Time will be extracted separately
                    artists=[title.strip()],
                    venue="The Independent",
                    url=event_url,
                )
                events.append(event)
            except (ValueError, TypeError):
                continue

        return events

    def _parse_js_event(self, event_info: dict) -> Optional[Event]:
        """Parse a single event from JavaScript event data"""
        try:
            # Extract date
            start_date = event_info.get("start", "")
            if not start_date:
                return None

            event_date = datetime.strptime(start_date, "%Y-%m-%d").date()

            # Extract title/artist
            title = event_info.get("title", "").strip()
            if not title:
                return None

            # Clean up HTML entities in title
            title = self._clean_html_entities(title)
            artists = [title]

            # Extract time from doors or displayTime
            event_time = None
            doors_text = event_info.get("doors", "")
            display_time = event_info.get("displayTime", "")

            # Try to extract time from either doors or show time
            time_text = doors_text or display_time
            if time_text:
                event_time = self._extract_time_from_text(time_text)

            # Create event URL - use the dialog ID if available
            event_url = "https://www.theindependentsf.com/calendar/"
            dialog_url = event_info.get("url", "")
            if dialog_url and dialog_url.startswith("#tw-event-dialog-"):
                event_url = f"https://www.theindependentsf.com/calendar/{dialog_url}"

            # Create the event
            event = Event(
                date=event_date,
                time=event_time,
                artists=artists,
                venue="The Independent",
                url=event_url,
            )

            return event

        except (ValueError, TypeError, KeyError) as e:
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
