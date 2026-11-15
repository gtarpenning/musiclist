"""Rockhouse Partners (RHP) WordPress events plugin, e.g. Boom Boom Room.

Cards are `.rhpSingleEvent` with `.singleEventDate` ("Sun, Nov 15"),
`.rhp-event__title--list`, and "Doors: 6 pm // Show: 7 pm" time text.
"""

import re
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Event

from .base import BaseScraper


class RockhouseScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        soup = BeautifulSoup(html_content, "lxml")
        events = []
        for card in soup.select(".rhpSingleEvent"):
            title = card.select_one(".rhp-event__title--list, #eventTitle h2")
            link = card.select_one("a.url[href]")
            when = card.select_one(".singleEventDate")
            if not (title and link and when):
                continue
            event_date = self.parse_date_text(when.get_text(" "))
            times = card.select_one(".rhp-event__time-text--list")
            times = times.get_text(" ") if times else ""
            show = re.search(r"show[^0-9]*(\d{1,2}(?::\d{2})?\s*[ap]\.?m)", times, re.I)
            event_time = self.parse_time_ampm(show.group(1) if show else times)
            cost_el = card.select_one(".rhp-event__cost--list, .eventCost")
            cost = (
                self.extract_price_from_text(cost_el.get_text(" ")) if cost_el else None
            )
            name = self.clean_text(title.get_text(" "))
            event = self.make_event(
                event_date,
                event_time,
                [name],
                urljoin(self.venue.base_url, link["href"]),
                cost,
            )
            if event:
                events.append(event)
        return events
