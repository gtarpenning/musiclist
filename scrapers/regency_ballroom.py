from datetime import datetime, date, time as dt_time
from typing import List, Optional
from bs4 import BeautifulSoup
import re
import json

from models import Event
from .base import BaseScraper


class RegencyBallroomScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from The Regency Ballroom's shows page"""
        soup = BeautifulSoup(html_content, "html.parser")
        events = []

        # The Regency Ballroom uses AXS/AEG system with JSON API
        # Look for the JSON API endpoint in the HTML
        axs_section = soup.find("div", class_="c-axs-events__container")

        if axs_section and axs_section.get("data-file"):
            json_url = axs_section.get("data-file")
            # Fetch JSON data from the API
            try:
                json_events = self._fetch_json_events(json_url)
                return json_events
            except Exception as e:
                print(f"Error fetching JSON events: {e}")

        # Fallback to HTML parsing if JSON fails
        event_elements = soup.find_all(
            "div", class_=re.compile(r".*event.*|.*show.*|.*calendar.*", re.I)
        )

        for element in event_elements:
            if self._is_valid_event_element(element):
                event = self._parse_single_event(element)
                if event:
                    events.append(event)

        return events

    def _fetch_json_events(self, json_url: str) -> List[Event]:
        """Fetch and parse events from JSON API"""
        import requests
        from datetime import datetime
        import time

        # Use much tighter timeout for external API calls
        timeout = 2
        max_retries = 2

        for attempt in range(max_retries):
            try:
                response = requests.get(json_url, headers=self.headers, timeout=timeout)
                response.raise_for_status()
                json_data = response.json()

                events = []
                for event_data in json_data.get("events", []):
                    event = self._parse_json_event(event_data)
                    if event:
                        events.append(event)

                return events

            except (requests.RequestException, ValueError) as e:
                if attempt == max_retries - 1:  # Last attempt
                    print(
                        f"Error fetching JSON from {json_url} after {max_retries} attempts: {e}"
                    )
                    return []
                else:
                    # Exponential backoff: wait 0.5s, then 1s
                    wait_time = 0.5 * (2**attempt)
                    print(
                        f"Attempt {attempt + 1} failed for {json_url}, retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)

    def _parse_json_event(self, event_data: dict) -> Optional[Event]:
        """Parse a single event from JSON data"""
        try:
            # Extract date and time
            event_datetime_str = event_data.get("eventDateTime")
            if not event_datetime_str or event_datetime_str.upper() == "TBD":
                return None

            try:
                # Handle different datetime formats
                if event_datetime_str.endswith("Z"):
                    event_datetime = datetime.fromisoformat(
                        event_datetime_str.replace("Z", "+00:00")
                    )
                else:
                    event_datetime = datetime.fromisoformat(event_datetime_str)

                event_date = event_datetime.date()
                event_time = event_datetime.time()
            except ValueError:
                # Skip events with invalid datetime
                return None

            # Extract artists
            title_data = event_data.get("title", {})
            artists = []

            # Main headliner
            headliner = title_data.get("headlinersText")
            if headliner and headliner.strip():
                artists.append(headliner.strip().upper())

            # Supporting acts
            supporting = title_data.get("supportingText")
            if supporting and supporting.strip():
                supporting_clean = supporting.strip()
                # Clean up supporting text (remove "with " prefix)
                supporting_clean = re.sub(
                    r"^with\s+", "", supporting_clean, flags=re.IGNORECASE
                )
                if supporting_clean:
                    # Split on common separators and clean
                    support_artists = self.clean_artist_names(supporting_clean)
                    artists.extend(support_artists)

            # If still no artists, try the main event title
            if not artists:
                event_title = title_data.get("eventTitleText")
                if event_title and event_title.strip():
                    artists.append(event_title.strip().upper())

            if not artists:
                return None

            # Extract cost information
            cost = None
            if event_data.get("ticketPrice"):
                price_info = event_data.get("ticketPrice", {})
                if isinstance(price_info, dict):
                    low_price = price_info.get("low")
                    high_price = price_info.get("high")
                    if low_price and high_price:
                        cost = f"${low_price}-${high_price}"
                    elif low_price:
                        cost = f"${low_price}"
                else:
                    cost = str(price_info)

            # Construct event URL
            event_url = self._construct_event_url(event_data)

            return Event(
                date=event_date,
                time=event_time,
                artists=artists,
                venue=self.venue.name,
                url=event_url,
                cost=cost,
            )

        except Exception as e:
            print(f"Error parsing JSON event: {e}")
            return None

    def _construct_event_url(self, event_data: dict) -> str:
        """Construct event URL from JSON data"""
        # Try to get the event URL from links
        links = event_data.get("links", {})
        if isinstance(links, dict):
            event_url = links.get("eventUrl") or links.get("ticketUrl")
            if event_url:
                return event_url

        # Fallback: construct URL from event ID
        event_id = event_data.get("eventId")
        if event_id:
            return f"https://www.theregencyballroom.com/events/{event_id}/"

        # Ultimate fallback
        return "https://www.theregencyballroom.com/shows/"

    def _is_valid_event_element(self, element) -> bool:
        """Check if element contains valid event data"""
        text = element.get_text().lower()
        # Look for indicators that this is an actual event
        return any(
            keyword in text for keyword in ["show", "concert", "event", "pm", "am", "$"]
        )

    def _parse_single_event(self, element) -> Optional[Event]:
        """Parse a single event from HTML element"""
        return self.parse_single_event(element)

    def _extract_date(self, element) -> Optional[date]:
        """Extract date from Regency Ballroom event element"""
        # Look for date information in various formats
        date_text = ""

        # Try different selectors for date information
        date_selectors = [
            {"class": re.compile(r".*date.*", re.I)},
            {"class": re.compile(r".*day.*", re.I)},
            {"class": re.compile(r".*time.*", re.I)},
        ]

        for selector in date_selectors:
            date_elem = element.find(["div", "span", "p"], selector)
            if date_elem:
                date_text = date_elem.get_text().strip()
                break

        if not date_text:
            # Fallback: search all text for date patterns
            full_text = element.get_text()
            date_match = re.search(r"(\w+,?\s+\w+\s+\d{1,2},?\s+\d{4})", full_text)
            if date_match:
                date_text = date_match.group(1)

        if date_text:
            # Try to parse different date formats
            parsed_date = self.parse_full_date_format(date_text)
            if parsed_date:
                return parsed_date

            # Try other date parsing methods if full format fails
            return self._parse_date_variants(date_text)

        return None

    def _parse_date_variants(self, date_text: str) -> Optional[date]:
        """Parse various date formats that might be used"""
        try:
            # Try MM/DD/YYYY format
            if re.match(r"\d{1,2}/\d{1,2}/\d{4}", date_text):
                return datetime.strptime(date_text, "%m/%d/%Y").date()

            # Try MM-DD-YYYY format
            if re.match(r"\d{1,2}-\d{1,2}-\d{4}", date_text):
                return datetime.strptime(date_text, "%m-%d-%Y").date()

            # Try YYYY-MM-DD format
            if re.match(r"\d{4}-\d{1,2}-\d{1,2}", date_text):
                return datetime.strptime(date_text, "%Y-%m-%d").date()

        except ValueError:
            pass

        return None

    def _extract_time(self, element) -> Optional[dt_time]:
        """Extract time from Regency Ballroom event element"""
        # Look for time information
        time_selectors = [
            {"class": re.compile(r".*time.*", re.I)},
            {"class": re.compile(r".*hour.*", re.I)},
            {"class": re.compile(r".*showtime.*", re.I)},
            {"class": re.compile(r".*door.*", re.I)},
        ]

        for selector in time_selectors:
            time_elem = element.find(["div", "span", "p"], selector)
            if time_elem:
                time_text = time_elem.get_text().strip()
                time_obj = self.parse_time_ampm(time_text)
                if time_obj:
                    return time_obj

        # Fallback: search all text for time patterns
        full_text = element.get_text()
        time_matches = re.findall(
            r"\b(\d{1,2}:?\d{0,2}\s*[ap]m)\b", full_text, re.IGNORECASE
        )

        for time_text in time_matches:
            time_obj = self.parse_time_ampm(time_text)
            if time_obj:
                return time_obj

        return None

    def _extract_artists(self, element) -> List[str]:
        """Extract artist names from Regency Ballroom event element"""
        artists = []

        # Look for artist information in various selectors
        artist_selectors = [
            {"class": re.compile(r".*artist.*", re.I)},
            {"class": re.compile(r".*title.*", re.I)},
            {"class": re.compile(r".*name.*", re.I)},
            {"class": re.compile(r".*performer.*", re.I)},
            {"class": re.compile(r".*headliner.*", re.I)},
        ]

        for selector in artist_selectors:
            artist_elem = element.find(
                ["h1", "h2", "h3", "h4", "div", "span", "p"], selector
            )
            if artist_elem:
                artist_text = artist_elem.get_text().strip()
                if artist_text and len(artist_text) > 2:  # Basic validation
                    # Clean and split artist names
                    cleaned_artists = self.clean_artist_names(artist_text)
                    if cleaned_artists:
                        artists.extend(cleaned_artists)
                        break

        # If no artists found through selectors, look for links or headings
        if not artists:
            # Look for main heading or title
            title_elem = element.find(["h1", "h2", "h3"])
            if title_elem:
                artist_text = title_elem.get_text().strip()
                if artist_text:
                    cleaned_artists = self.clean_artist_names(artist_text)
                    if cleaned_artists:
                        artists.extend(cleaned_artists)

        return artists

    def _extract_url(self, element) -> Optional[str]:
        """Extract event URL from Regency Ballroom event element"""
        # Look for links within the event element
        link = element.find("a", href=True)
        if link:
            url = link["href"]

            # If it's a relative URL, make it absolute
            if url.startswith("/"):
                return f"https://www.theregencyballroom.com{url}"
            elif url.startswith("http"):
                return url

        # Look for ticket links or event detail links
        ticket_links = element.find_all(
            "a", href=True, string=re.compile(r"ticket|buy|details", re.I)
        )
        for link in ticket_links:
            url = link["href"]
            if url.startswith("/"):
                return f"https://www.theregencyballroom.com{url}"
            elif url.startswith("http"):
                return url

        # Default URL if no specific event URL found
        return "https://www.theregencyballroom.com/shows/"

    def _extract_cost(self, element) -> Optional[str]:
        """Extract ticket cost from Regency Ballroom event element"""
        return self.extract_cost_generic(element)
