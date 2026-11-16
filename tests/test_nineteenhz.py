"""Offline tests for the 19hz.info listing: parsing, the venue scraper, and price filling."""

import sys
import threading
import unittest
from datetime import date, time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import Event, Venue  # noqa: E402
from scrapers import nineteenhz  # noqa: E402
from scrapers.base import BaseScraper  # noqa: E402
from scrapers.nineteenhz import (  # noqa: E402
    LISTING_URL,
    NineteenHzScraper,
    fill_prices,
    parse_listings,
    same_venue,
    venue_key,
)

# Rows copied from the live page's two tables (dated events, then weekly
# nights), including its unclosed <td> and the "Price | Age" cell.
PAGE = """
<table><tbody>
<tr><td>Sat: Nov 28 <br/>(10pm-3am)</td><td><a href="https://ra.co/events/2540793">Polyglamorous X Squish</a> @ The Great Northern (San Francisco)</td><td>house, techno, disco</td><td>$20 b4 11 / $30 | 21+</td><td></td><td></td><td><div class="shrink">2026/11/28</div></td></tr>
<tr><td>Fri: Nov 27 <br/>(9pm-2am)</td><td><a href="https://ra.co/events/1">Loft Sessions</a> @ Public Works Loft (San Francisco)<td>techno</td><td>$15 | 21+</td><td></td><td></td><td><div class="shrink">2026/11/27</div></td></tr>
<tr><td>Fri: Nov 27 <br/>(10pm-4am)</td><td><a href="https://ra.co/events/2">Deep End: Mira Kalix</a> @ Public Works (San Francisco)</td><td>house</td><td>$25-$35 | 21+</td><td></td><td></td><td><div class="shrink">2026/11/27</div></td></tr>
<tr><td>Sun: Nov 29 <br/>(1am-6am)</td><td><a href="https://posh.vip/e/after">Afters</a> @ Audio (San Francisco)</td><td>house</td><td>$10 | 21+</td><td></td><td></td><td><div class="shrink">2026/11/29</div></td></tr>
<tr><td>Sat: Nov 28 <br/>(9pm)</td><td><a href="https://example.com/tba">Secret Party</a> @ TBA (San Francisco)</td><td>house</td><td></td><td></td><td></td><td><div class="shrink">2026/11/28</div></td></tr>
</tbody></table>
<table><tbody>
<tr class="even"><td>Mondays <br/>(9:30pm-2:30am)</td><td><a href="https://www.dnalounge.com/">Death Guild</a> @ DNA Lounge (San Francisco)</td><td>goth, industrial</td><td>$5 b4 1030/$8 | 21+</td><td></td><td></td></tr>
</tbody></table>
"""


def scraper(name="19hz.info"):
    return NineteenHzScraper(
        Venue(name, "https://19hz.info", "/eventlisting_BayArea.php")
    )


def show(venue, day, artists, cost=None):
    return Event(
        day,
        time(21, 0),
        artists,
        venue,
        f"https://{venue.replace(' ', '')}.example/",
        cost,
    )


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.listings = parse_listings(PAGE, scraper())

    def test_reads_both_tables(self):
        self.assertEqual(len(self.listings), 6)
        first = self.listings[0]
        self.assertEqual(first.title, "Polyglamorous X Squish")
        self.assertEqual(first.venue, "The Great Northern")
        self.assertEqual(first.date, date(2026, 11, 28))
        self.assertEqual(first.time, time(22, 0))
        self.assertEqual(first.price, "$20 b4 11 / $30")
        self.assertEqual(first.url, "https://ra.co/events/2540793")

    def test_weekly_night(self):
        weekly = self.listings[-1]
        self.assertIsNone(weekly.date)
        self.assertEqual(weekly.weekday, 0)
        self.assertEqual(weekly.time, time(21, 30))
        self.assertEqual(weekly.price, "$5 b4 1030/$8")

    def test_unclosed_cell_and_missing_price(self):
        loft = self.listings[1]
        self.assertEqual(
            (loft.title, loft.venue, loft.price),
            ("Loft Sessions", "Public Works Loft", "$15"),
        )
        self.assertIsNone(self.listings[4].price)

    def test_venue_names(self):
        self.assertEqual(
            venue_key("The Great American Music Hall (San Francisco)"),
            "great american music hall",
        )
        self.assertEqual(venue_key("Audio"), "audio nightclub")
        self.assertTrue(same_venue("Public Works Loft", "Public Works"))
        self.assertTrue(same_venue("Monarch - Upstairs Lounge", "Monarch"))
        self.assertFalse(same_venue("Public Worksop", "Public Works"))


class ScraperTest(unittest.TestCase):
    def test_keeps_one_venues_dated_shows(self):
        events = scraper("The Great Northern").parse_events(PAGE)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(
            (e.venue, e.date, e.artists, e.cost),
            (
                "The Great Northern",
                date(2026, 11, 28),
                ["Polyglamorous X Squish"],
                "$20 b4 11 / $30",
            ),
        )
        self.assertEqual(e.url, "https://ra.co/events/2540793")

    def test_fetches_the_page_once_per_process(self):
        calls = []

        def fake_fetch(self, url=None):
            calls.append(url)
            return PAGE

        with (
            mock.patch.object(nineteenhz, "_page", {}),
            mock.patch.object(BaseScraper, "fetch_page", fake_fetch),
        ):
            threads = [
                threading.Thread(target=scraper(n).scrape)
                for n in ("The Great Northern", "Monarch")
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(len(nineteenhz.fetch_listings()), 6)
        self.assertEqual(calls, [LISTING_URL])


class FillPricesTest(unittest.TestCase):
    def setUp(self):
        self.listings = parse_listings(PAGE, scraper())

    def test_matches_on_a_shared_title_word(self):
        # two Public Works listings that night; the title picks the right room
        deep = show("Public Works", date(2026, 11, 27), ["Mira Kalix", "Opener"])
        loft = show("Public Works", date(2026, 11, 27), ["Loft Sessions"])
        self.assertEqual(fill_prices([deep, loft], self.listings), 2)
        self.assertEqual((deep.cost, loft.cost), ("$25-$35", "$15"))

    def test_no_title_overlap_and_ambiguous_night_stays_empty(self):
        e = show("Public Works", date(2026, 11, 27), ["Somebody Else"])
        self.assertEqual(fill_prices([e], self.listings), 0)
        self.assertIsNone(e.cost)

    def test_lone_show_each_side_matches_without_title(self):
        e = show("The Great Northern", date(2026, 11, 28), ["Different Billing"])
        self.assertEqual(fill_prices([e], self.listings), 1)
        self.assertEqual(e.cost, "$20 b4 11 / $30")

    def test_after_midnight_listing_prices_the_night_before(self):
        e = show("Audio Nightclub", date(2026, 11, 28), ["Afters"])
        fill_prices([e], self.listings)
        self.assertEqual(e.cost, "$10")

    def test_weekly_night_needs_the_title(self):
        monday = date(2026, 11, 30)
        guild = show("DNA Lounge", monday, ["Death Guild"])
        other = show("DNA Lounge", monday, ["Touring Band"])
        self.assertEqual(fill_prices([guild, other], self.listings), 1)
        self.assertEqual((guild.cost, other.cost), ("$5 b4 1030/$8", None))

    def test_keeps_existing_prices(self):
        e = show("The Great Northern", date(2026, 11, 28), ["Polyglamorous"], "$22")
        self.assertEqual(fill_prices([e], self.listings), 0)
        self.assertEqual(e.cost, "$22")


if __name__ == "__main__":
    unittest.main()
