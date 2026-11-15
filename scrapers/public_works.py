"""Public Works: `div.event-item` cards linking to Tixr, with ISO datetimes."""

import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Event

from .base import BaseScraper


class PublicWorksScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        soup = BeautifulSoup(html_content, "lxml")
        events = []
        for item in soup.select("div.event-item"):
            link = item.select_one("a[href]")
            title = item.select_one(".event-title")
            if not (link and title):
                continue
            stamps = [t["datetime"] for t in item.select("time[datetime]")]
            timed = next((s for s in stamps if "T" in s), None)
            event_date, event_time = self.parse_iso_datetime(
                timed or (stamps[0] if stamps else "")
            )
            name = self.clean_text(title.get_text(" "))
            # "Sina Bathaie | White Lotus World Tour: Back Together" -> act first
            parts = [p.strip() for p in re.split(r"\s+\|\s+", name) if p.strip()]
            artists = [parts[0]] if parts else [name]
            event = self.make_event(
                event_date,
                event_time,
                artists,
                urljoin(self.venue.base_url, link["href"]),
            )
            if event:
                events.append(event)
        return events
