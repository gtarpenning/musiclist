from datetime import datetime, date, time as dt_time
from typing import List, Optional
from bs4 import BeautifulSoup
import re

from models import Event
from .base import BaseScraper


class NeckOfTheWoodsScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from Neck of the Woods calendar page"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # Be more specific about event containers to avoid duplicates
        # Look for actual event containers first - try common event markup patterns
        event_containers = []

        # Try specific selectors that are more likely to be actual event containers
        selectors_to_try = [
            '[class*="event"]',  # Any class containing "event"
            '[class*="show"]',  # Any class containing "show"
            '[class*="concert"]',  # Any class containing "concert"
            "article",  # Article tags often contain events
            '[class*="listing"]',  # Event listings
            '[class*="item"]',  # Event items
        ]

        for selector in selectors_to_try:
            containers = soup.select(selector)
            for container in containers:
                text = container.get_text().lower()
                # Only include if it has event-like content
                if (
                    any(keyword in text for keyword in ["show:", "doors:", "pm", "am"])
                    and len(text.strip()) > 20
                ):
                    event_containers.append(container)

        # If still no containers found, fall back to broader search but be more selective
        if not event_containers:
            potential_containers = soup.find_all(["div", "article", "section"])
            for container in potential_containers:
                text = container.get_text().lower()
                # More strict criteria to avoid duplicates
                if (
                    any(keyword in text for keyword in ["show:", "doors:", "pm", "am"])
                    and len(text.strip()) > 30  # Longer minimum text
                    and ("$" in text or "free" in text)
                ):  # Must have price info or be explicitly free
                    event_containers.append(container)

        # Parse events from selected containers
        raw_events = []
        for element in event_containers:
            event = self._parse_single_event(element)
            if event:
                raw_events.append(event)

        # Deduplicate events based on date, cleaned artists, and URL
        events = self._deduplicate_events(raw_events)
        return events

    def _deduplicate_events(self, events: List[Event]) -> List[Event]:
        """Remove duplicate events based on date and URL, keeping the best version"""
        # Group events by date and URL
        groups = {}
        for event in events:
            key = (event.date, event.url)
            if key not in groups:
                groups[key] = []
            groups[key].append(event)

        deduplicated = []
        for group in groups.values():
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                # Multiple events with same date/URL - pick the best one
                best_event = self._pick_best_event(group)
                deduplicated.append(best_event)

        return deduplicated

    def _pick_best_event(self, events: List[Event]) -> Event:
        """Pick the best event from a group of duplicates with same date/URL"""
        # Scoring criteria:
        # 1. Fewer artists is often better (less likely to be a mega-list)
        # 2. Artists without time prefixes are preferred
        # 3. Avoid artists that are just times like "8:00PM"

        scored_events = []
        for event in events:
            score = 0

            # Count time-like artists (bad)
            time_artists = len(
                [
                    a
                    for a in event.artists
                    if re.match(r"^\d{1,2}:\d{2}\s*(AM|PM)$", a, re.IGNORECASE)
                ]
            )
            score -= time_artists * 10

            # Prefer shorter artist lists (avoiding mega-lists)
            if len(event.artists) <= 5:
                score += 20
            elif len(event.artists) <= 10:
                score += 10
            else:
                score -= len(event.artists)  # Penalize very long lists

            # Prefer events without time prefixes in artist names
            clean_artists = 0
            for artist in event.artists:
                if not re.match(r"^\d{1,2}:\d{2}\s*(AM|PM)", artist, re.IGNORECASE):
                    clean_artists += 1
            score += clean_artists * 2

            scored_events.append((score, event))

        # Return the highest scoring event
        scored_events.sort(key=lambda x: x[0], reverse=True)
        return scored_events[0][1]

    def _parse_single_event(self, element) -> Optional[Event]:
        """Parse a single event from HTML element"""
        return self.parse_single_event(element)

    def _extract_date(self, element) -> Optional[date]:
        """Extract date from Neck of the Woods event element"""
        # Look for date patterns in various formats
        text = element.get_text()

        # Try to find date patterns like "Sun, Jul 20", "Fri Aug 1", "Aug.01.2025"
        date_patterns = [
            r"(\w{3}),?\s+(\w{3})\s+(\d{1,2})",  # "Sun, Jul 20" or "Fri Aug 1"
            r"(\w{3})\.(\d{2})\.(\d{4})",  # "Aug.01.2025"
            r"(\w+)\s+(\d{1,2}),?\s+(\d{4})",  # "August 1, 2025"
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if "." in pattern:  # Aug.01.2025 format
                        month_str, day_str, year_str = match.groups()
                        month = self.month_name_to_number(month_str)
                        if month:
                            return date(int(year_str), month, int(day_str))
                    else:  # Other formats
                        parts = match.groups()
                        if len(parts) == 3:
                            # Could be day_name, month, day OR month, day, year
                            if parts[2].isdigit() and len(parts[2]) == 4:  # year
                                month = self.month_name_to_number(parts[0])
                                if month:
                                    return date(int(parts[2]), month, int(parts[1]))
                            else:  # day format
                                month = self.month_name_to_number(parts[1])
                                if month:
                                    current_year = datetime.now().year
                                    return date(current_year, month, int(parts[2]))
                except (ValueError, AttributeError):
                    continue

        return None

    def _extract_time(self, element) -> Optional[dt_time]:
        """Extract time from Neck of the Woods event element"""
        text = element.get_text()

        # Look for time patterns like "8:00 pm", "Show: 7:00 pm", "Doors: 6:00 pm"
        time_patterns = [
            r"Show:\s*(\d{1,2}:?\d{0,2})\s*(pm|am)",
            r"(\d{1,2}:?\d{0,2})\s*(pm|am)",
        ]

        for pattern in time_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                time_str = match.group(1) + " " + match.group(2)
                parsed_time = self.parse_time_ampm(time_str)
                if parsed_time:
                    return parsed_time

        return None

    def _extract_artists(self, element) -> List[str]:
        """Extract artist names from Neck of the Woods event element"""
        # Look for artist names in various places
        artists = []

        # Try to find artist names in links or headings
        artist_links = element.find_all("a")
        for link in artist_links:
            link_text = link.get_text().strip()
            # Skip obvious navigation links
            if link_text and not any(
                skip in link_text.lower()
                for skip in ["more info", "buy tickets", "calendar", "contact"]
            ):
                artists.extend(self.clean_artist_names(link_text))

        # If no artists found in links, try headings
        if not artists:
            headings = element.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
            for heading in headings:
                heading_text = heading.get_text().strip()
                if heading_text:
                    artists.extend(self.clean_artist_names(heading_text))

        # If still no artists, try to extract from the general text
        if not artists:
            text = element.get_text()
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            for line in lines:
                # Look for lines that might be artist names (not dates, times, or prices)
                if (
                    not re.search(r"\d{1,2}:\d{2}", line)  # no times
                    and not re.search(r"\$\d+", line)  # no prices
                    and not re.search(
                        r"(doors|show|pm|am)", line, re.I
                    )  # no door/show times
                    and len(line) > 3  # reasonable length
                ):
                    potential_artists = self.clean_artist_names(line)
                    if potential_artists:
                        artists.extend(
                            potential_artists[:1]
                        )  # Take first artist from line
                        break  # Only take the first reasonable line

        return list(set(artists)) if artists else []

    def _extract_url(self, element) -> Optional[str]:
        """Extract event URL from Neck of the Woods element"""
        # Look for "More Info" or "Buy Tickets" links
        links = element.find_all("a", href=True)

        for link in links:
            link_text = link.get_text().lower()
            if any(
                keyword in link_text
                for keyword in ["more info", "buy tickets", "details"]
            ):
                href = link.get("href")
                if href:
                    # Make sure it's a full URL
                    if href.startswith("http"):
                        return href
                    elif href.startswith("/"):
                        return f"https://www.neckofthewoodssf.com{href}"
                    else:
                        return f"https://www.neckofthewoodssf.com/{href}"

        # If no specific ticket links found, try any link that looks like an event link
        for link in links:
            href = link.get("href")
            if href and ("event" in href or "show" in href or "concert" in href):
                if href.startswith("http"):
                    return href
                elif href.startswith("/"):
                    return f"https://www.neckofthewoodssf.com{href}"
                else:
                    return f"https://www.neckofthewoodssf.com/{href}"

        return None

    def _extract_cost(self, element) -> Optional[str]:
        """Extract ticket cost from Neck of the Woods event element"""
        text = element.get_text()

        # Look for price patterns
        cost = self.extract_price_from_text(text)
        if cost:
            return cost

        # Check for common free indicators
        if any(keyword in text.lower() for keyword in ["free", "$0.00", "no cover"]):
            return "Free"

        return None
