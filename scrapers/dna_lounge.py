"""DNA Lounge: hand-rolled month grids at /calendar/YYYY/MM.html.

Each show is an `a.ccell` linking to a day page like "11-06.html" (or
"11-06d.html" for a second event that night); the year comes from the
month page itself.
"""

import re
from datetime import date
from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta

from models import Event

from .base import BaseScraper

MONTHS_AHEAD = 3


class DnaLoungeScraper(BaseScraper):
    def month_url(self, month_start: date) -> str:
        return urljoin(
            self.venue.base_url,
            f"calendar/{month_start.year}/{month_start.month:02d}.html",
        )

    def scrape(self) -> List[Event]:
        first = date.today().replace(day=1)
        events: List[Event] = []
        for offset in range(MONTHS_AHEAD):
            month_start = first + relativedelta(months=offset)
            url = self.month_url(month_start)
            try:
                html = self.fetch_page(url)
            except Exception:
                if offset == 0:
                    raise
                break  # Future months often aren't published yet
            events.extend(self.parse_month(html, url, month_start.year))
        return self.dedupe_events(events)

    def parse_events(self, html_content: str) -> List[Event]:
        today = date.today()
        return self.parse_month(
            html_content, self.month_url(today.replace(day=1)), today.year
        )

    def parse_month(self, html_content: str, page_url: str, year: int) -> List[Event]:
        soup = BeautifulSoup(html_content, "lxml")
        heading = soup.select_one("h1")
        m = re.search(r"\b(\d{4})\b", heading.get_text(" ")) if heading else None
        if m:
            year = int(m.group(1))
        events = []
        for cell in soup.select("a.ccell[href]"):
            href = cell["href"]
            dm = re.search(r"(\d{2})-(\d{2})[a-z]?\.html", href)
            if not dm:
                continue
            try:
                event_date = date(year, int(dm.group(1)), int(dm.group(2)))
            except ValueError:
                continue
            body = cell.find("div") or cell
            for tag in body.find_all(["b", "i"]):
                tag.extract()
            title = self.clean_text(body.get_text(" "))
            if not title:
                continue
            artists = self.split_lineup(title) if " + " in title else [title]
            event = self.make_event(event_date, None, artists, urljoin(page_url, href))
            if event:
                events.append(event)
        return events
