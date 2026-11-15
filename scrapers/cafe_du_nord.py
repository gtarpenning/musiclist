"""Café du Nord and the Swedish American Hall upstairs share one listing
(cafedunord.com/shows); each card carries data-room="cdn" or "sah"."""

from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Event

from .base import BaseScraper


class CafeDuNordScraper(BaseScraper):
    room: Optional[str] = "cdn"

    def parse_events(self, html_content: str) -> List[Event]:
        soup = BeautifulSoup(html_content, "lxml")
        events = []
        for card in soup.select("li.bill-card"):
            if self.room and card.get("data-room") != self.room:
                continue
            link = card.select_one(".bill-card__name a[href]")
            if not link:
                continue
            when = card.select_one("time.bill-card__date[datetime]")
            event_date, event_time = self.parse_iso_datetime(
                when["datetime"] if when else card.get("data-date", "")
            )
            support = []
            for act in card.select(".bill-card__support .act"):
                support.extend(self.split_lineup(act.get_text(" ")))
            url = urljoin(self.venue.base_url, link["href"])
            event = self.make_event(
                event_date,
                event_time,
                [self.clean_text(link.get_text(" "))] + support,
                url,
            )
            if event:
                events.append(event)
        return events


class SwedishAmericanHallScraper(CafeDuNordScraper):
    room = "sah"
