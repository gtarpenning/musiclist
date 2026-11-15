"""DICE event-list widget.

Venues embed `DiceEventListWidget.create({...})` with a public, client-side
API key plus venue/promoter filters. The widget itself calls DICE's
partners API with that key; we do the same, reading the config from the
venue's own page each run so key rotations don't break anything. Used for
Kilowatt, The Knockout and Halcyon.
"""

import html as html_lib
import json
import re
from typing import List, Optional

from models import Event

from .base import BaseScraper, ScrapeError

API_URL = "https://partners-endpoint.dice.fm/api/v2/events"
MAX_PAGES = 5


class DiceScraper(BaseScraper):
    def widget_config(self, page_html: str) -> dict:
        text = html_lib.unescape(page_html)
        m = re.search(r"DiceEventListWidget\.create\(\s*(\{.*?\})\s*\)", text, re.S)
        if not m:
            raise ScrapeError(f"No DICE widget found on {self.find_calendar_url()}")
        try:
            cfg = json.loads(m.group(1))
        except json.JSONDecodeError as e:
            raise ScrapeError(f"Unreadable DICE widget config: {e}")
        if not cfg.get("apiKey"):
            raise ScrapeError("DICE widget config has no apiKey")
        return cfg

    def scrape(self) -> List[Event]:
        cfg = self.widget_config(self.fetch_page())
        params = [("page[size]", "50"), ("types", "linkout,event")]
        for key in ("venues", "promoters", "artists", "tags"):
            for value in cfg.get(key) or []:
                params.append((f"filter[{key}][]", value))
        headers = {"x-api-key": cfg["apiKey"]}

        events: List[Event] = []
        for page in range(1, MAX_PAGES + 1):
            page_params = params + ([("page[number]", str(page))] if page > 1 else [])
            data = self.fetch_json(API_URL, params=page_params, headers=headers)
            for item in data.get("data") or []:
                event = self._to_event(item)
                if event:
                    events.append(event)
            if not (data.get("links") or {}).get("next"):
                break
        return self.dedupe_events(events)

    def parse_events(self, html_content: str) -> List[Event]:
        # DICE data comes from the API, not the page; see scrape()
        return []

    def _to_event(self, item: dict) -> Optional[Event]:
        if (
            "cancelled" in (item.get("flags") or [])
            or item.get("status") == "cancelled"
        ):
            return None
        event_date, event_time = self.parse_iso_datetime(item.get("date") or "")
        name = self.clean_text(item.get("name") or "")
        extras = [
            a
            for a in (item.get("artists") or [])
            if isinstance(a, str) and a.lower() not in name.lower()
        ]
        artists = [name] + extras
        return self.make_event(
            event_date, event_time, artists, item.get("url"), self._price(item)
        )

    @staticmethod
    def _price(item: dict) -> Optional[str]:
        totals = []
        for ticket in item.get("ticket_types") or []:
            price = (ticket.get("price") or {}).get("total")
            if isinstance(price, (int, float)):
                totals.append(price / 100)
        if not totals:
            return None
        lo, hi = min(totals), max(totals)
        if hi == 0:
            return "Free"
        fmt = lambda p: f"${p:.0f}" if p == int(p) else f"${p:.2f}"
        return fmt(lo) if lo == hi else f"{fmt(lo)}-{fmt(hi)}"
