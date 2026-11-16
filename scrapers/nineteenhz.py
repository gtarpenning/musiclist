"""19hz.info: the community-run Bay Area electronic music listing.

One public HTML page with two tables. The first lists dated events (date and
time, "Title @ Venue (City)", tags, "Price | Age", organizers, links, a
sortable yyyy/mm/dd); the second lists weekly nights ("Mondays (9:30pm)").
It is used two ways:

- NineteenHzScraper reads a venue's calendar from 19hz, for clubs without a
  scrapable site of their own (The Great Northern, Monarch).
- fill_prices() adds prices to shows our own scrapers found without one.
  Tixr-ticketed venues such as Public Works answer scripts with a captcha;
  19hz lists the same shows with prices.

It's a volunteer-run site, so a process fetches the page once (see
NineteenHzScraper.fetch_page) however many venues and fills read it.
"""

import re
import threading
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Iterable, List, Optional

from bs4 import BeautifulSoup

from models import Event, Venue

from .base import BaseScraper

LISTING_URL = "https://19hz.info/eventlisting_BayArea.php"
_page: dict = {}  # this process's copy of the listing page
_page_lock = threading.Lock()  # venues scrape in parallel; the first one fetches

# 19hz spellings that don't reduce to ours by normalising (see venue_key)
ALIASES = {"audio": "audio nightclub", "envelop at the midway": "midway"}
WEEKDAYS = [
    "mondays",
    "tuesdays",
    "wednesdays",
    "thursdays",
    "fridays",
    "saturdays",
    "sundays",
]
# words too common in show titles to say two titles are the same show
STOPWORDS = set(
    "the and with feat featuring presents present live tour night party dj djs b2b "
    "all ages san francisco free tickets edition vol special guest guests".split()
)


@dataclass
class Listing:
    title: str
    venue: str  # as 19hz writes it, without "(City)"
    date: Optional[date]  # None for a weekly night
    weekday: Optional[int]  # 0 = Monday, weekly nights only
    time: Optional[time]
    price: Optional[str]
    url: Optional[str]


def fold(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    )


def venue_key(name: str) -> str:
    """'The Great American Music Hall (San Francisco)' -> 'great american music hall'."""
    key = re.sub(r"\(.*?\)", " ", fold(name)).replace("&", " and ")
    key = re.sub(r"[^a-z0-9]+", " ", key).strip()
    key = re.sub(r"^the ", "", key)
    return ALIASES.get(key, key)


def same_venue(listing_venue: str, our_venue: str) -> bool:
    """Exact match, or a named room of the venue ('Public Works Loft', 'Monarch - Upstairs Lounge')."""
    theirs, ours = venue_key(listing_venue), venue_key(our_venue)
    return theirs == ours or theirs.startswith(ours + " ")


def title_tokens(text: str) -> set:
    return {
        t
        for t in re.findall(r"[a-z0-9]+", fold(text))
        if len(t) >= 3 and t not in STOPWORDS
    }


def parse_listings(html: str, scraper: BaseScraper) -> List[Listing]:
    soup = BeautifulSoup(html, "lxml")
    listings = []
    for tr in soup.select("table tbody tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        when = scraper.clean_text(cells[0].get_text(" "))
        link = cells[1].find("a", href=True)
        text = scraper.clean_text(cells[1].get_text(" "))
        if " @ " not in text:
            continue
        # "Title @ Venue (City)"; split on the last " @ " ("Popscene @ Rickshaw Stop (SF)")
        left, venue = text.rsplit(" @ ", 1)
        title = scraper.clean_text(link.get_text(" ")) if link else left
        venue = re.sub(r"\s*\([^)]*\)\s*$", "", venue).strip()

        price_text = scraper.clean_text(cells[3].get_text(" "))
        price = price_text.split("|")[0].strip() or None
        hours = re.search(r"\(([^)]*)\)", when)
        start = scraper.parse_time_ampm(hours.group(1).split("-")[0]) if hours else None
        href = (
            link["href"]
            if link and link["href"].startswith(("http://", "https://"))
            else None
        )

        sortable = tr.select_one("div.shrink")
        stamp = (
            re.match(r"(\d{4})/(\d{2})/(\d{2})", sortable.get_text(strip=True))
            if sortable
            else None
        )
        weekly = next(
            (i for i, day in enumerate(WEEKDAYS) if when.lower().startswith(day)), None
        )
        if stamp:
            listings.append(
                Listing(
                    title,
                    venue,
                    date(*map(int, stamp.groups())),
                    None,
                    start,
                    price,
                    href,
                )
            )
        elif weekly is not None:
            listings.append(Listing(title, venue, None, weekly, start, price, href))
    return listings


class NineteenHzScraper(BaseScraper):
    """A venue's dated events, read from 19hz (weekly nights are left out: any week may be off)."""

    def find_calendar_url(self) -> str:
        return LISTING_URL

    def fetch_page(self, url: Optional[str] = None) -> str:
        with _page_lock:
            if "html" not in _page:
                _page["html"] = super().fetch_page(LISTING_URL)
            return _page["html"]

    def parse_events(self, html_content: str) -> List[Event]:
        events = []
        for listing in parse_listings(html_content, self):
            if listing.date is None or not same_venue(listing.venue, self.venue.name):
                continue
            event = self.make_event(
                listing.date,
                listing.time,
                [listing.title],
                listing.url or LISTING_URL,
                listing.price,
            )
            if event:
                events.append(event)
        return self.dedupe_events(events)


def fetch_listings() -> List[Listing]:
    """Every listing on the page, for fill_prices()."""
    scraper = NineteenHzScraper(
        Venue("19hz.info", "https://19hz.info", "/eventlisting_BayArea.php")
    )
    return parse_listings(scraper.fetch_page(), scraper)


def fill_prices(events: Iterable[Event], listings: List[Listing]) -> int:
    """Set `cost` on events that have none, from matching 19hz listings. Returns how many were filled.

    A listing matches an event at the same venue on the same date (a listing
    starting before 6am may also be the previous night's show) when their
    titles share a distinctive word, or when each side has exactly one show
    at that venue that night. Weekly nights need the shared word too.
    """
    events = list(events)
    per_night = Counter((e.venue, e.date) for e in events)
    by_venue = defaultdict(list)
    for listing in listings:
        if listing.price:
            by_venue[venue_key(listing.venue)].append(listing)

    def candidates(event: Event) -> List[Listing]:
        ours = venue_key(event.venue)
        found = []
        for key, group in by_venue.items():
            if key == ours or key.startswith(ours + " "):
                found += group
        return found

    filled = 0
    for event in events:
        if event.cost:
            continue
        pool = candidates(event)
        if not pool:
            continue
        dated = [
            l for l in pool
            if l.date == event.date
            or (l.date and l.time and l.time.hour < 6 and l.date - timedelta(days=1) == event.date)
        ]  # fmt: skip
        weekly = [
            l for l in pool if l.date is None and l.weekday == event.date.weekday()
        ]
        ours = title_tokens(" ".join(event.artists))

        match = None
        scored = sorted(
            (
                (len(ours & title_tokens(l.title)), i)
                for i, l in enumerate(dated + weekly)
            ),
            reverse=True,
        )
        if (
            scored
            and scored[0][0] > 0
            and (len(scored) == 1 or scored[1][0] < scored[0][0])
        ):
            match = (dated + weekly)[scored[0][1]]
        elif len(dated) == 1 and per_night[(event.venue, event.date)] == 1:
            match = dated[0]
        if match:
            event.cost = match.price
            filled += 1
    return filled
