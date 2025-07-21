from datetime import datetime, date
from typing import List, Optional
from bs4 import BeautifulSoup, NavigableString
import re

from models import Event
from .base import BaseScraper


class BottomOfTheHillScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from Bottom of the Hill's calendar page"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # Find all table rows that contain event data
        # Events are in table rows with background-color: rgb(204, 204, 51)
        event_rows = soup.find_all(
            "td", {"style": lambda x: x and "background-color: rgb(204, 204, 51)" in x}
        )

        for td in event_rows:
            event = self._parse_single_event_new_format(td)
            if event:
                events.append(event)

        return events

    def _parse_single_event_new_format(self, element) -> Optional[Event]:
        """Parse a single event from the new HTML format"""
        try:
            # Extract date
            event_date = self._extract_date_new_format(element)
            if not event_date:
                return None

            # Extract time
            event_time = self._extract_time_new_format(element)

            # Extract artists
            artists = self._extract_artists_new_format(element)

            # Extract cost
            cost = self._extract_cost_new_format(element)

            # Extract URL - look for event detail links
            url = self._extract_url_new_format(element)

            if not artists:
                return None

            return Event(
                date=event_date,
                time=event_time,
                artists=artists,
                venue=self.venue.name,
                url=url,
                cost=cost,
            )
        except Exception as e:
            print(f"Error parsing event: {e}")
            return None

    def _extract_date_new_format(self, element) -> Optional[date]:
        """Extract date from the new HTML format"""
        # Look for elements with class="date"
        date_spans = element.find_all("span", class_="date")

        for span in date_spans:
            date_text = span.get_text().strip()

            # Pattern: "Sunday July 20 2025" or "Tuesday July 22 2025"
            date_pattern = r"(\w+)\s+(\w+)\s+(\d+)\s+(\d{4})"
            match = re.search(date_pattern, date_text)

            if match:
                try:
                    day_name, month_name, day, year = match.groups()
                    month_num = self.month_name_to_number(month_name)

                    if month_num:
                        return date(int(year), month_num, int(day))

                except (ValueError, AttributeError):
                    pass

        return None

    def _extract_time_new_format(self, element):
        """Extract time from the new HTML format"""
        # Look for elements with class="time"
        time_spans = element.find_all("span", class_="time")

        for span in time_spans:
            time_text = span.get_text().strip()

            # Pattern: "8:00PM" or "9:00PM"
            time_pattern = r"(\d{1,2}):(\d{2})(PM|AM)"
            match = re.search(time_pattern, time_text, re.IGNORECASE)

            if match:
                hour, minute, am_pm = match.groups()
                return self.parse_time_ampm(f"{hour}:{minute} {am_pm}")

            # Also try simpler pattern for times like "8PM"
            simple_pattern = r"(\d{1,2})(PM|AM)"
            simple_match = re.search(simple_pattern, time_text, re.IGNORECASE)
            if simple_match:
                hour, am_pm = simple_match.groups()
                return self.parse_time_ampm(f"{hour}:00 {am_pm}")

        return None

    def _extract_artists_new_format(self, element) -> List[str]:
        """Extract artist names from the new HTML format"""
        artists = []

        # Look for elements with class="band"
        band_elements = element.find_all(class_="band")

        for band_elem in band_elements:
            band_name = band_elem.get_text().strip()
            if band_name:
                # Clean up the band name
                cleaned_name = re.sub(r"\s+", " ", band_name).strip()
                if cleaned_name and cleaned_name not in artists:
                    artists.append(cleaned_name)

        return artists

    def _extract_url_new_format(self, element) -> Optional[str]:
        """Extract event URL from the new HTML format"""
        # Look for detail links - typically have "details.png" or specific event URLs
        links = element.find_all("a", href=True)

        for link in links:
            href = link["href"]

            # Look for event detail pages (like "/20250720.html")
            if re.match(r".*\/\d{8}\.html$", href):
                # Make sure it's an absolute URL
                if href.startswith("http"):
                    return href
                else:
                    return f"https://www.bottomofthehill.com{href.lstrip('/')}"

        # If no specific event URL, return the venue's main page
        return self.venue.base_url

    def _extract_cost_new_format(self, element) -> Optional[str]:
        """Extract ticket cost from the new HTML format"""
        # Look for elements with class="cover"
        cover_spans = element.find_all(class_="cover")

        cost_parts = []
        for span in cover_spans:
            cost_text = span.get_text().strip()
            if cost_text:
                cost_parts.append(cost_text)

        if cost_parts:
            full_cost_text = " ".join(cost_parts)

            # Look for dollar amounts
            dollar_match = re.search(r"\$\d+", full_cost_text)
            if dollar_match:
                # Try to capture the full pricing info (like "$17 in advance / $20 at the door")
                price_pattern = r"\$\d+[^/]*(?:/[^$]*\$\d+[^/]*)?"
                price_match = re.search(price_pattern, full_cost_text)
                if price_match:
                    return price_match.group(0).strip()
                else:
                    return dollar_match.group(0)

            # Check for "free" shows
            if "free" in full_cost_text.lower():
                return "Free"

        return None

    # Keep the legacy parsing methods for backward compatibility with tests
    def _parse_single_event(self, element) -> Optional[Event]:
        """Legacy method - delegates to new format parser"""
        return self._parse_single_event_new_format(element)

    def _extract_date(self, element) -> Optional[date]:
        """Legacy method - delegates to new format parser"""
        return self._extract_date_new_format(element)

    def _extract_time(self, element):
        """Legacy method - delegates to new format parser"""
        return self._extract_time_new_format(element)

    def _extract_artists(self, element) -> List[str]:
        """Legacy method - delegates to new format parser"""
        return self._extract_artists_new_format(element)

    def _extract_url(self, element) -> Optional[str]:
        """Legacy method - delegates to new format parser"""
        return self._extract_url_new_format(element)

    def _extract_cost(self, element) -> Optional[str]:
        """Legacy method - delegates to new format parser"""
        return self._extract_cost_new_format(element)
