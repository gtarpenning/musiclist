"""1015 Folsom: server-rendered `article.calendar-row` cards with an ISO date."""

from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Event

from .base import BaseScraper


class Folsom1015Scraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        soup = BeautifulSoup(html_content, "lxml")
        events = []
        for row in soup.select("article.calendar-row"):
            when = row.select_one("time[datetime]")
            link = row.select_one("a.calendar-event-link[href]") or row.select_one(
                "h3 a[href]"
            )
            if not (when and link):
                continue
            event_date, event_time = self.parse_iso_datetime(when["datetime"])
            title = self.clean_text(link.get_text(" "))
            # "THROTTLE TECHNO: DJ Stingray" -> keep the night name and the act
            artists = [title]
            event = self.make_event(
                event_date,
                event_time,
                artists,
                urljoin(self.venue.base_url, link["href"]),
            )
            if event:
                events.append(event)
        return events
