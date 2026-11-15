"""TicketWeb / Ticketmaster WordPress plugin ("tw-plugin-upcoming-event-list").

Used by Brick & Mortar, The Independent, Neck of the Woods, Bimbo's 365
and August Hall. Every site skins it differently, but the inner class
names (tw-section, tw-name, tw-event-date, tw-event-time, tw-price) are
stable. Date text varies: "11.15", "Sun, Nov 15", "Tuesday, November 17,
2026", or separate month/day spans.
"""

from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Event

from .base import BaseScraper

MAX_PAGES = 12


class TicketWebScraper(BaseScraper):
    # Last resolved date, carried across pages so yearless dates keep moving forward
    _last_date = None

    def scrape(self) -> List[Event]:
        url = self.find_calendar_url()
        events: List[Event] = []
        visited = set()
        self._last_date = None
        for _ in range(MAX_PAGES):
            if not url or url in visited:
                break
            visited.add(url)
            html = self.fetch_page(url)
            events.extend(self.parse_events(html))
            url = self._next_page(html, url)
        return self.dedupe_events(events)

    def _next_page(self, html: str, current: str) -> Optional[str]:
        soup = BeautifulSoup(html, "lxml")
        nxt = soup.select_one("a.next.page-numbers[href]")
        return urljoin(current, nxt["href"]) if nxt else None

    def parse_events(self, html_content: str) -> List[Event]:
        soup = BeautifulSoup(html_content, "lxml")
        sections = []
        for section in soup.select("div.tw-section"):
            month = self._text(section, ".tw-event-month")
            day_text = self._text(section, ".tw-event-date")
            parts = self.parse_month_day(f"{month} {day_text}" if month else day_text)
            if parts:
                sections.append((section, parts))

        dates = self.assign_years_in_order(
            [p for _, p in sections], previous=self._last_date
        )
        events = []
        for (section, _), event_date in zip(sections, dates):
            if event_date:
                self._last_date = event_date
            event = self._parse_section(section, event_date)
            if event:
                events.append(event)
        return events

    def _text(self, el, selector) -> str:
        found = el.select_one(selector)
        return self.clean_text(found.get_text(" ")) if found else ""

    def _parse_section(self, section, event_date) -> Optional[Event]:
        link = section.select_one(".tw-name a[href]")
        if not link:
            return None
        url = urljoin(self.venue.base_url, link["href"])
        headliner = self.clean_text(link.get_text(" "))

        support = [
            self.clean_text(s.get_text(" "))
            for s in section.select(".tw-attractions span")
        ]
        if not support:
            support = self.split_lineup(self._text(section, ".tw-attractions"))

        event_time = self.parse_time_ampm(
            self._text(section, ".tw-event-time")
        ) or self.parse_time_ampm(self._text(section, ".tw-event-door-time"))
        cost = self.extract_price_from_text(self._text(section, ".tw-price"))

        return self.make_event(event_date, event_time, [headliner] + support, url, cost)
