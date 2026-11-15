"""schema.org Event data embedded as JSON-LD.

The most drift-resistant source there is: sites keep it valid for search
engines through redesigns. Used for The Midway, The Fillmore and The
Masonic.
"""

import json
import re
from typing import Iterable, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from models import Event

from .base import BaseScraper

# Bundles and upsells that Live Nation lists alongside real shows
SKIP_NAMES = re.compile(
    r"\b(parking|upgrade|add[- ]?on|package|multi[- ]?show|gift card|merch)\b|\(\d+\)\s*show ticket",
    re.I,
)
STATUS_SKIP = ("EventCancelled",)


def _iter_events(node) -> Iterable[dict]:
    if isinstance(node, list):
        for item in node:
            yield from _iter_events(item)
    elif isinstance(node, dict):
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if any(isinstance(t, str) and t.endswith("Event") for t in types):
            yield node
        for key in ("@graph", "itemListElement", "item", "subEvent", "event", "events"):
            if key in node:
                yield from _iter_events(node[key])


class JsonLdScraper(BaseScraper):
    # Optional: only keep events whose location name matches (case-insensitive substring)
    location_filter: Optional[str] = None

    def parse_events(self, html_content: str) -> List[Event]:
        soup = BeautifulSoup(html_content, "lxml")
        events = []
        for script in soup.find_all("script", type=re.compile("ld\\+json", re.I)):
            try:
                data = json.loads(script.string or script.get_text() or "")
            except (json.JSONDecodeError, TypeError):
                continue
            for item in _iter_events(data):
                event = self._to_event(item)
                if event:
                    events.append(event)
        return events

    def _to_event(self, item: dict) -> Optional[Event]:
        name = self.clean_text(item.get("name") or "")
        if not name or SKIP_NAMES.search(name):
            return None
        if any(s in str(item.get("eventStatus", "")) for s in STATUS_SKIP):
            return None
        if self.location_filter:
            location = item.get("location") or {}
            loc_name = (
                location.get("name", "")
                if isinstance(location, dict)
                else str(location)
            )
            if self.location_filter.lower() not in loc_name.lower():
                return None

        event_date, event_time = self.parse_iso_datetime(item.get("startDate") or "")
        url = item.get("url") or item.get("@id") or ""
        if isinstance(url, list):
            url = url[0] if url else ""
        url = urljoin(self.venue.base_url, url) if url else self.find_calendar_url()

        return self.make_event(
            event_date, event_time, self._artists(name, item), url, self._price(item)
        )

    def _artists(self, name: str, item: dict) -> List[str]:
        # "Artist: The Big Tour", "Artist - Live in SF" -> "Artist"
        headline = re.sub(
            r"(?:\s*[:|]|\s+[-–—])\s+[^-–—:|]*\b(tour|live|presents|night \w+)\b.*$",
            "",
            name,
            flags=re.I,
        )
        artists = [headline.strip() or name]
        performers = item.get("performer") or []
        performers = performers if isinstance(performers, list) else [performers]
        for p in performers:
            pname = p.get("name") if isinstance(p, dict) else p
            if isinstance(pname, str) and pname.strip().lower() not in headline.lower():
                artists.append(pname.strip())
        return artists

    def _price(self, item: dict) -> Optional[str]:
        offers = item.get("offers")
        offers = offers if isinstance(offers, list) else [offers] if offers else []
        prices = []
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            for key in ("price", "lowPrice", "highPrice"):
                try:
                    value = float(offer.get(key))
                except (TypeError, ValueError):
                    continue
                prices.append(value)
        prices = sorted({p for p in prices if p >= 0})
        if not prices:
            return None
        if prices[-1] == 0:
            return "Free"
        fmt = lambda p: f"${p:g}" if p == int(p) else f"${p:.2f}"
        return (
            fmt(prices[0])
            if len(prices) == 1
            else f"{fmt(prices[0])}-{fmt(prices[-1])}"
        )
