"""SeeTickets WordPress plugin (wl.seetickets.us white-label listings).

Used by The Chapel, Rickshaw Stop, Hotel Utah and Great American Music Hall. The plugin renders two
views on the same page: a list view that pages over AJAX 10 events at a
time, and month-grid calendars that contain every announced show. The
grid is the complete source; list cards add price and support acts for
the first page, merged in by ticket URL.
"""

import re
from datetime import date
from typing import Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Event

from .base import BaseScraper

SKIP_TITLES = re.compile(r"^\W*(private event|closed|private party|cancell?ed)\b", re.I)


class SeeTicketsScraper(BaseScraper):
    def parse_events(self, html_content: str) -> List[Event]:
        soup = BeautifulSoup(html_content, "lxml")
        details = self._list_details(soup)

        events = self._grid_events(soup, details)
        if not events:
            events = [d["event"] for d in details.values() if d.get("event")]
        return events

    # -- month grid ------------------------------------------------------

    def _grid_events(self, soup, details: Dict[str, dict]) -> List[Event]:
        events = []
        month = year = None
        for node in soup.select(
            ".seetickets-calendar-year-month-container, table.seetickets-calendar"
        ):
            if "seetickets-calendar-year-month-container" in (node.get("class") or []):
                m = re.search(r"([A-Za-z]+)\s+(\d{4})", node.get_text(" "))
                month = self.month_name_to_number(m.group(1)) if m else None
                year = int(m.group(2)) if m else None
                continue
            if not (month and year):
                continue
            for cell in node.select("td"):
                day_el = cell.select_one(".date-number")
                if not day_el or not day_el.get_text(strip=True).isdigit():
                    continue
                try:
                    event_date = date(year, month, int(day_el.get_text(strip=True)))
                except ValueError:
                    continue
                for box in cell.select(".seetickets-calendar-event-container"):
                    link = box.select_one(
                        ".seetickets-calendar-event-title a[href]"
                    ) or box.select_one("a[href]")
                    if not link:
                        continue
                    title = self.clean_text(link.get_text(" "))
                    if SKIP_TITLES.match(title):
                        continue
                    url = urljoin(self.venue.base_url, link["href"])
                    info = details.get(url, {})
                    event_time = self._show_time(
                        self._field(box, ".seetickets-calendar-event-date")
                    )
                    artists = info.get("artists") or self.split_lineup(title) or [title]
                    event = self.make_event(
                        event_date, event_time, artists, url, info.get("cost")
                    )
                    if event:
                        events.append(event)
        return events

    # -- list cards --------------------------------------------------------

    def _list_details(self, soup) -> Dict[str, dict]:
        details = {}
        for card in soup.select(".seetickets-list-event-container"):
            link = card.select_one(".event-title a[href]") or card.select_one(
                "a[href*='seetickets']"
            )
            if not link:
                continue
            url = urljoin(self.venue.base_url, link["href"])
            title = self.clean_text(link.get_text(" "))
            if SKIP_TITLES.match(title):
                continue

            headliners = self._field(card, ".headliners") or title
            support = self._field(card, ".supporting-talent")
            artists = self.split_lineup(headliners) + self.split_lineup(support)

            date_text = self._field(card, ".event-date") or self._field(card, ".date")
            event_date = self.parse_date_text(date_text)
            event_time = self.parse_time_ampm(
                self._field(card, ".see-showtime")
            ) or self._show_time(self._field(card, ".doortime-showtime"))
            cost = self.extract_price_from_text(
                self._field(card, ".ages-price") or self._field(card, ".price")
            )

            details[url] = {
                "artists": artists,
                "cost": cost,
                "event": self.make_event(
                    event_date, event_time, artists or [title], url, cost
                ),
            }
        return details

    def _field(self, card, selector) -> str:
        el = card.select_one(selector)
        return self.clean_text(el.get_text(" ")) if el else ""

    def _show_time(self, text: str):
        m = re.search(r"show[^0-9]*(\d{1,2}(?::\d{2})?\s*[ap]\.?m)", text or "", re.I)
        return self.parse_time_ampm(m.group(1)) if m else self.parse_time_ampm(text)
