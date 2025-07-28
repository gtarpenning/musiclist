from datetime import datetime, date, time as dt_time
from typing import List, Optional
import json
import requests
from urllib.parse import urljoin

from models import Event
from .base import BaseScraper


class MidwayScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        """Parse events from The Midway's JSON API"""
        # The Midway uses a JSON API, so we'll fetch directly from the API endpoint
        api_url = urljoin(self.venue.base_url, "wp-json/tixr/v1/events")

        # Use tighter timeout and retry logic for external API calls
        timeout = 2
        max_retries = 2

        for attempt in range(max_retries):
            try:
                # Fetch JSON data from API
                response = requests.get(api_url, headers=self.headers, timeout=timeout)
                response.raise_for_status()

                events_data = response.json()

                if not isinstance(events_data, list):
                    print(f"Unexpected API response format from {self.venue.name}")
                    return []

                break  # Success, exit retry loop

            except (requests.RequestException, json.JSONDecodeError) as e:
                if attempt == max_retries - 1:  # Last attempt
                    print(
                        f"Error fetching JSON data from {api_url} after {max_retries} attempts: {e}"
                    )
                    return []
                else:
                    # Exponential backoff: wait 0.5s, then 1s
                    import time

                    wait_time = 0.5 * (2**attempt)
                    print(
                        f"Attempt {attempt + 1} failed for {api_url}, retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)

        events = []
        for event_data in events_data:
            try:
                event = self._parse_json_event(event_data)
                if event:
                    events.append(event)
            except Exception as e:
                print(f"Error parsing event: {e}")
                continue

        return events

    def _parse_json_event(self, event_data: dict) -> Optional[Event]:
        """Parse a single event from JSON data"""
        try:
            # Extract and validate event name
            name = event_data.get("name", "").strip()
            if not name:
                return None

            # Extract and parse date/time
            start_date_ms = event_data.get("start_date")
            if not start_date_ms:
                return None

            try:
                # Convert milliseconds to datetime
                event_datetime = datetime.fromtimestamp(start_date_ms / 1000)
                event_date = event_datetime.date()
                event_time = event_datetime.time()
            except (ValueError, TypeError):
                return None

            # Extract artists from lineups
            artists = self._extract_artists_from_json(event_data)
            if not artists:
                # Fallback to event name if no lineup artists found
                artists = self.clean_artist_names(name)

            if not artists:
                return None

            # Extract event URL
            event_url = event_data.get("url", "").strip()
            if not event_url:
                return None

            # Extract cost information
            cost = self._extract_cost_from_json(event_data)

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

    def _extract_artists_from_json(self, event_data: dict) -> List[str]:
        """Extract artist names from JSON event data"""
        artists = []

        # Get artists from lineups
        lineups = event_data.get("lineups", [])
        for lineup in lineups:
            acts = lineup.get("acts", [])
            for act in acts:
                artist_info = act.get("artist", {})
                artist_name = artist_info.get("name", "").strip()
                if artist_name:
                    artists.append(artist_name.upper())

        return artists

    def _extract_cost_from_json(self, event_data: dict) -> Optional[str]:
        """Extract cost information from JSON event data"""
        sales = event_data.get("sales", [])

        if not sales:
            return None

        prices = []
        for sale in sales:
            # Skip sold out or unavailable tickets
            state = sale.get("state", "").upper()
            if state in ["SOLD_OUT", "CLOSED"]:
                continue

            current_price = sale.get("current_price", 0)
            if current_price is not None and current_price > 0:
                prices.append(float(current_price))

        if not prices:
            # Check if it's a free event
            for sale in sales:
                current_price = sale.get("current_price", 0)
                if current_price == 0:
                    return "Free"
            return None

        if len(prices) == 1:
            return f"${prices[0]:.0f}"
        elif len(prices) > 1:
            min_price = min(prices)
            max_price = max(prices)
            if min_price == max_price:
                return f"${min_price:.0f}"
            else:
                return f"${min_price:.0f}-${max_price:.0f}"

        return None

    # Base class abstract methods - not used since we override parse_events
    def _extract_date(self, element) -> Optional[date]:
        """Not used - we parse directly from JSON"""
        return None

    def _extract_time(self, element) -> Optional[dt_time]:
        """Not used - we parse directly from JSON"""
        return None

    def _extract_artists(self, element) -> List[str]:
        """Not used - we parse directly from JSON"""
        return []

    def _extract_url(self, element) -> Optional[str]:
        """Not used - we parse directly from JSON"""
        return None
