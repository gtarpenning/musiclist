"""Gray Area (grayarea.org/visit/events/).

The page has two `section.featured-items` blocks: upcoming events in date
order, then a "Past" block in reverse order. Only the first is parsed.
Dates are bare "MM/DD"; times and prices aren't on the listing.
"""

import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Event

from .base import BaseScraper

TITLE_PREFIXES = re.compile(r"^(SOLD OUT!?|Workshop)\s*", re.I)


class GrayAreaScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        soup = BeautifulSoup(html_content, "lxml")
        items = []
        for section in soup.select("section.featured-items"):
            heading = section.find(["h2", "h3"])
            if heading and heading.get_text(strip=True).lower() == "past":
                continue
            for item in section.select("div.item"):
                date_el = item.select_one("div.date")
                parts = self.parse_month_day(date_el.get_text(" ")) if date_el else None
                if parts:
                    items.append((item, parts))

        dates = self.assign_years_in_order([p for _, p in items])
        events = []
        for (item, _), event_date in zip(items, dates):
            event = self._parse_item(item, event_date)
            if event:
                events.append(event)
        return events

    def _parse_item(self, item, event_date) -> Optional[Event]:
        link = item.select_one("a.item-link[href]")
        title_el = item.select_one(".item-title")
        if not link or not title_el:
            return None
        title = self.clean_text(title_el.get_text(" "))
        cost = "Sold Out" if "SOLD OUT" in title.upper() else None
        artists = self._artists(TITLE_PREFIXES.sub("", title))
        url = urljoin(self.venue.base_url, link["href"])
        return self.make_event(event_date, None, artists, url, cost)

    @staticmethod
    def _artists(title: str) -> List[str]:
        # The "artist" is usually the event title; split only on clear separators
        if re.search(r"\s+with\s+", title, re.I):
            parts = re.split(r"\s+with\s+", title, flags=re.I)
        elif " + " in title:
            parts = title.split(" + ")
        else:
            parts = [title]
        return [p.strip().upper() for p in parts if p.strip()]
