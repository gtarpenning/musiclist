"""Another Planet Entertainment WordPress theme (billgrahamcivic.com).

Each listing has `.date-show[content="November 24, 2026 8:00pm"]`, a
`.show-title`, and an optional `.topline` (tour name).
"""

from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Event

from .base import BaseScraper


class AnotherPlanetScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        soup = BeautifulSoup(html_content, "lxml")
        events = []
        for block in soup.select(".content-information"):
            title = block.select_one(".show-title")
            link = block.select_one("a[href*='/events/']")
            when = block.select_one(".date-show[content]")
            if not (title and link and when):
                continue
            stamp = when["content"]
            event_date = self.parse_date_text(stamp)
            show = block.select_one(".event__start-time")
            event_time = self.parse_time_ampm(
                show.get_text(" ") if show else ""
            ) or self.parse_time_ampm(stamp)
            artists = self.split_lineup(title.get_text(" ")) or [
                self.clean_text(title.get_text(" "))
            ]
            event = self.make_event(
                event_date,
                event_time,
                artists,
                urljoin(self.venue.base_url, link["href"]),
            )
            if event:
                events.append(event)
        return events
