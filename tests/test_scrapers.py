"""Offline tests for the shared scrapers, date logic, pruning and numbering.

Fixtures are small hand-written snippets that mirror each platform's
markup (TicketWeb, SeeTickets, JSON-LD, DICE, Café du Nord, Gray Area),
so these run without the network. `music doctor` covers the live sites.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import date, time, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import Event, Venue
from scrapers.base import BaseScraper
from scrapers.cafe_du_nord import CafeDuNordScraper, SwedishAmericanHallScraper
from scrapers.dice import DiceScraper
from scrapers.gray_area import GrayAreaScraper
from scrapers.jsonld import JsonLdScraper
from scrapers.seetickets import SeeTicketsScraper
from scrapers.ticketweb import TicketWebScraper
from storage.database import Database


def venue(name="Test Venue", base="https://example.com"):
    return Venue(name=name, base_url=base, calendar_path="/calendar/")


class PlainScraper(BaseScraper):
    def parse_events(self, html_content):
        return []


class DateLogicTest(unittest.TestCase):
    def setUp(self):
        self.s = PlainScraper(venue())
        self.today = date(2026, 11, 15)

    def order(self, pairs, previous=None):
        return self.s.assign_years_in_order(
            [(m, d, None) for m, d in pairs], previous=previous, today=self.today
        )

    def test_parse_month_day_formats(self):
        p = self.s.parse_month_day
        self.assertEqual(p("11.15"), (11, 15, None))
        self.assertEqual(p("Sun, Nov 15"), (11, 15, None))
        self.assertEqual(p("Tuesday, November 17, 2026"), (11, 17, 2026))
        self.assertEqual(p("15 Nov 2026"), (11, 15, 2026))
        self.assertEqual(p("2027-01-04"), (1, 4, 2027))
        self.assertEqual(p("11/15/26"), (11, 15, 2026))
        self.assertIsNone(p("TBA"))
        self.assertIsNone(p("13.40"))

    def test_series_that_started_recently_stays_this_year(self):
        # A weekly night listed from two weeks ago must not jump to next year
        self.assertEqual(
            self.order([(11, 1), (11, 8), (11, 15)]),
            [date(2026, 11, d) for d in (1, 8, 15)],
        )

    def test_listing_wraps_into_next_year(self):
        got = self.order([(11, 20), (12, 31), (1, 2), (10, 20)])
        self.assertEqual(
            got,
            [
                date(2026, 11, 20),
                date(2026, 12, 31),
                date(2027, 1, 2),
                date(2027, 10, 20),
            ],
        )

    def test_first_entry_months_ago_means_next_year(self):
        self.assertEqual(self.order([(5, 20)]), [date(2027, 5, 20)])

    def test_new_year_lookback(self):
        s = self.s.assign_years_in_order(
            [(12, 28, None), (1, 5, None)], today=date(2027, 1, 3)
        )
        self.assertEqual(s, [date(2026, 12, 28), date(2027, 1, 5)])

    def test_small_backstep_is_not_a_wrap(self):
        # Interleaved lists step back a few days; that must not add a year
        self.assertEqual(
            self.order([(11, 20), (11, 18)]), [date(2026, 11, 20), date(2026, 11, 18)]
        )

    def test_explicit_year_wins_and_carries(self):
        got = self.s.assign_years_in_order(
            [(3, 1, 2027), (3, 5, None)], today=self.today
        )
        self.assertEqual(got, [date(2027, 3, 1), date(2027, 3, 5)])

    def test_previous_carries_across_pages(self):
        self.assertEqual(
            self.order([(1, 9)], previous=date(2026, 12, 30)), [date(2027, 1, 9)]
        )

    def test_parse_iso_datetime_converts_to_pacific(self):
        d, t = self.s.parse_iso_datetime("2026-11-21T04:00:00Z")
        self.assertEqual((d, t), (date(2026, 11, 20), time(20, 0)))
        d, t = self.s.parse_iso_datetime("2026-11-20T00:00:00-08:00")
        self.assertEqual((d, t), (date(2026, 11, 20), None))  # midnight = no time given

    def test_split_lineup(self):
        split = self.s.split_lineup
        self.assertEqual(
            split("Armored Saint/ Metal Church, Livekill"),
            ["Armored Saint", "Metal Church", "Livekill"],
        )
        self.assertEqual(split("AC/DC"), ["AC/DC"])
        self.assertEqual(split("Simon & Garfunkel"), ["Simon & Garfunkel"])
        self.assertEqual(split("with Foo + Bar"), ["Foo", "Bar"])

    def test_dedupe_artists_cleans_lineups(self):
        dedupe = self.s.dedupe_artists
        # plugin field labels are dropped
        self.assertEqual(
            dedupe(["Margaret Glaspy", "Supporting Talent: Anna Tivel"]),
            ["Margaret Glaspy", "Anna Tivel"],
        )
        # a "support" entry that only restates the headliner is dropped
        self.assertEqual(dedupe(["Starpine", "Starpine : LIVE"]), ["Starpine"])
        self.assertEqual(dedupe(["KAUFMANN", "Kaufmann (DE)"]), ["KAUFMANN"])
        self.assertEqual(
            dedupe(["Chelsea Cutler", "Chelsea Cutler - IS THIS THE END? Tour"]),
            ["Chelsea Cutler"],
        )
        self.assertEqual(dedupe(["Bob", "Bob Mould"]), ["Bob", "Bob Mould"])
        # comma-joined entries dedupe the way storage will split them
        self.assertEqual(
            dedupe(["HUG", "Devendra Banhart, Noah Georgeson", "Noah Georgeson"]),
            ["HUG", "Devendra Banhart", "Noah Georgeson"],
        )

    def test_parse_time_and_price(self):
        self.assertEqual(self.s.parse_time_ampm("Show 8pm"), time(20, 0))
        self.assertEqual(self.s.parse_time_ampm("7:30 PM"), time(19, 30))
        self.assertEqual(self.s.extract_price_from_text("$15 - $25"), "$15 - $25")
        self.assertEqual(self.s.extract_price_from_text("FREE w/ RSVP"), "Free")


TICKETWEB_PAGE = """
<div class="tw-section"><div class="tw-event-date">11.29</div>
  <div class="tw-name"><a href="/tm-event/headliner/">Headliner</a></div>
  <div class="tw-attractions"><span>Opener One</span><span>Opener Two</span></div>
  <span class="tw-event-time">Show: 8:00 pm</span><span class="tw-price">$20.00</span></div>
<div class="tw-section"><div class="tw-event-date">12.31</div>
  <div class="tw-name"><a href="/tm-event/nye/">NYE Party</a></div>
  <span class="tw-event-door-time">Doors: 9:00 pm</span></div>
<div class="tw-section"><div class="tw-event-date">01.02</div>
  <div class="tw-name"><a href="/tm-event/jan/">January Band</a></div></div>
<a class="next page-numbers" href="/calendar/page/2/">Next</a>
"""


class TicketWebTest(unittest.TestCase):
    def test_parse_sections_and_year_wrap(self):
        s = TicketWebScraper(venue())
        with patch.object(
            BaseScraper,
            "anchor_date",
            staticmethod(lambda m, d, today=None: date(2026, m, d)),
        ):
            events = s.parse_events(TICKETWEB_PAGE)
        self.assertEqual(
            [e.date for e in events],
            [date(2026, 11, 29), date(2026, 12, 31), date(2027, 1, 2)],
        )
        first = events[0]
        self.assertEqual(first.artists, ["Headliner", "Opener One", "Opener Two"])
        self.assertEqual(first.url, "https://example.com/tm-event/headliner/")
        self.assertEqual(first.time, time(20, 0))
        self.assertEqual(first.cost, "$20.00")
        self.assertEqual(events[1].time, time(21, 0))  # door time fallback

    def test_next_page(self):
        s = TicketWebScraper(venue())
        nxt = s._next_page(TICKETWEB_PAGE, "https://example.com/calendar/")
        self.assertEqual(nxt, "https://example.com/calendar/page/2/")


SEETICKETS_PAGE = """
<div class="seetickets-list-event-container">
  <p class="event-title"><a href="https://wl.seetickets.us/event/big-show/1">Big Show</a></p>
  <p class="headliners">Big Show</p><p class="supporting-talent">Small Band, Tiny Band</p>
  <p class="event-date">Fri Dec 4</p><span class="see-showtime">8:00PM</span>
  <span class="ages-price">21+ | $25.00</span></div>
<div class="seetickets-calendar-year-month-container">December 2026</div>
<table class="seetickets-calendar"><tr>
 <td><div class="date-number">04</div>
   <div class="seetickets-calendar-event-container">
     <div class="seetickets-calendar-event-title"><a href="https://wl.seetickets.us/event/big-show/1">Big Show</a></div>
     <div class="seetickets-calendar-event-date">Show 8:00PM</div></div>
   <div class="seetickets-calendar-event-container">
     <div class="seetickets-calendar-event-title"><a href="https://wl.seetickets.us/event/private/2">Private Event</a></div></div></td>
 <td><div class="date-number">05</div>
   <div class="seetickets-calendar-event-container">
     <div class="seetickets-calendar-event-title"><a href="https://wl.seetickets.us/event/grid/3">Grid Act/ Other Act, Third</a></div>
     <div class="seetickets-calendar-event-date">Show 7:00PM</div></div>
   <div class="seetickets-calendar-event-container">
     <div class="seetickets-calendar-event-title"><a href="https://wl.seetickets.us/event/x/4">*CANCELLED* Gone Band</a></div></div></td>
</tr></table>
"""


class SeeTicketsTest(unittest.TestCase):
    def test_grid_merged_with_list_details(self):
        events = SeeTicketsScraper(venue()).parse_events(SEETICKETS_PAGE)
        self.assertEqual(len(events), 2)  # private + cancelled skipped
        big, grid = events
        self.assertEqual(big.date, date(2026, 12, 4))
        self.assertEqual(big.artists, ["Big Show", "Small Band", "Tiny Band"])
        self.assertEqual(big.cost, "$25.00")
        self.assertEqual(big.time, time(20, 0))
        self.assertEqual(grid.artists, ["Grid Act", "Other Act", "Third"])
        self.assertEqual(grid.time, time(19, 0))


JSONLD_PAGE = """<script type="application/ld+json">%s</script>""" % json.dumps(
    {
        "@graph": [
            {
                "@type": "MusicEvent",
                "name": "Star Act - The Big World Tour",
                "startDate": "2026-12-12T20:00:00-08:00",
                "url": "https://example.com/e/star",
                "performer": [{"name": "Star Act"}, {"name": "Support Act"}],
                "offers": [{"price": "45.00"}, {"price": "89.50"}],
            },
            {
                "@type": "Event",
                "name": "Parking: Star Act",
                "startDate": "2026-12-12T18:00:00-08:00",
                "url": "/p",
            },
            {
                "@type": "Event",
                "name": "Star Act - SIX (6) Show Ticket",
                "startDate": "2026-12-12T18:00:00-08:00",
                "url": "/6",
            },
            {
                "@type": "MusicEvent",
                "name": "Rapper: The Joyrider Tour",
                "startDate": "2026-12-14T20:00:00-08:00",
                "url": "/r",
            },
            {
                "@type": "Event",
                "name": "Cancelled Act",
                "startDate": "2026-12-13T20:00:00-08:00",
                "url": "/c",
                "eventStatus": "https://schema.org/EventCancelled",
            },
        ]
    }
)


class JsonLdTest(unittest.TestCase):
    def test_events_skip_upsells_and_cancellations(self):
        events = JsonLdScraper(venue()).parse_events(JSONLD_PAGE)
        self.assertEqual([e.artists[0] for e in events], ["Star Act", "Rapper"])
        e = events[0]
        self.assertEqual(e.artists, ["Star Act", "Support Act"])
        self.assertEqual((e.date, e.time), (date(2026, 12, 12), time(20, 0)))
        self.assertEqual(e.cost, "$45-$89.50")


class DiceTest(unittest.TestCase):
    def test_widget_config_and_event(self):
        s = DiceScraper(venue())
        page = "<script>DiceEventListWidget.create({&quot;apiKey&quot;:&quot;k123&quot;,&quot;venues&quot;:[&quot;Kilowatt&quot;]})</script>"
        self.assertEqual(s.widget_config(page)["apiKey"], "k123")
        item = {
            "name": "Loud Band",
            "date": "2026-12-02T03:30:00Z",
            "url": "https://dice.fm/event/abc",
            "artists": ["Loud Band", "Quiet Band"],
            "ticket_types": [{"price": {"total": 1500}}, {"price": {"total": 2000}}],
        }
        e = s._to_event(item)
        self.assertEqual(e.artists, ["Loud Band", "Quiet Band"])
        self.assertEqual((e.date, e.time), (date(2026, 12, 1), time(19, 30)))
        self.assertEqual(e.cost, "$15-$20")
        self.assertIsNone(s._to_event({**item, "flags": ["cancelled"]}))


CAFE_PAGE = """
<li class="bill-card" data-room="cdn"><time class="bill-card__date" datetime="2026-11-20T20:00:00-08:00"></time>
  <h3 class="bill-card__name"><a href="/shows/a">Room Act</a></h3>
  <div class="bill-card__support"><span class="act">Opener</span></div></li>
<li class="bill-card" data-room="sah"><time class="bill-card__date" datetime="2026-11-21T19:00:00-08:00"></time>
  <h3 class="bill-card__name"><a href="/shows/b">Hall Act</a></h3></li>
"""


class CafeDuNordTest(unittest.TestCase):
    def test_rooms_are_split(self):
        cdn = CafeDuNordScraper(venue("Café du Nord")).parse_events(CAFE_PAGE)
        sah = SwedishAmericanHallScraper(venue("Swedish American Hall")).parse_events(
            CAFE_PAGE
        )
        self.assertEqual([e.artists for e in cdn], [["Room Act", "Opener"]])
        self.assertEqual([e.artists for e in sah], [["Hall Act"]])
        self.assertEqual(cdn[0].time, time(20, 0))


GRAY_AREA_PAGE = """
<section class="p2 featured-items"><div class="wrap">
  <div class="item"><a class="item-link" href="/event/one/"></a><div class="date">12/01</div><h5 class="item-title">Talk One</h5></div>
  <div class="item"><a class="item-link" href="/event/two/"></a><div class="date">01/14</div><h5 class="item-title">SOLD OUT! Concert with Guest</h5></div>
</div></section>
<section class="p2 featured-items"><h3>Past</h3><div class="wrap">
  <div class="item"><a class="item-link" href="/event/old/"></a><div class="date">11/10</div><h5 class="item-title">Old Thing</h5></div>
</div></section>
"""


class GrayAreaTest(unittest.TestCase):
    def test_skips_past_section(self):
        with patch.object(
            BaseScraper,
            "anchor_date",
            staticmethod(lambda m, d, today=None: date(2026, m, d)),
        ):
            events = GrayAreaScraper(
                venue("Gray Area", "https://grayarea.org")
            ).parse_events(GRAY_AREA_PAGE)
        self.assertEqual(
            [e.date for e in events], [date(2026, 12, 1), date(2027, 1, 14)]
        )
        self.assertEqual(events[1].artists, ["CONCERT", "GUEST"])
        self.assertEqual(events[1].cost, "Sold Out")
        self.assertEqual(events[0].url, "https://grayarea.org/event/one/")


class DatabaseBehaviourTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "test.db"))
        self.db.save_venue(
            Venue(
                name="The Chapel",
                base_url="https://thechapelsf.com",
                calendar_path="/calendar/",
            )
        )
        self.soon = date.today() + timedelta(days=1)

    def tearDown(self):
        self.tmp.cleanup()

    def ev(self, name, days=1):
        return Event(
            date=date.today() + timedelta(days=days),
            time=None,
            artists=[name],
            venue="The Chapel",
            url=f"https://x/{name}",
        )

    def names(self):
        return sorted(
            e.artists_display for e in self.db.get_events(venues=["The Chapel"])
        )

    def test_prune_drops_vanished_unpinned_but_keeps_pins(self):
        self.db.save_events([self.ev("keep"), self.ev("gone"), self.ev("pinned")])
        pinned = next(e for e in self.db.get_events() if e.artists_display == "pinned")
        self.db.pin_event(pinned.id)

        self.db.save_events([self.ev("keep"), self.ev("new")], prune_missing=True)
        self.assertEqual(self.names(), ["keep", "new", "pinned"])

    def test_resave_preserves_pin(self):
        self.db.save_events([self.ev("act")])
        e = self.db.get_events()[0]
        self.db.pin_event(e.id)
        self.db.save_events([self.ev("act")], prune_missing=True)
        self.assertTrue(self.db.get_events()[0].pinned)

    def test_starring_unscraped_venue(self):
        from venues_config import star_venue, get_starred_venues

        # Kilowatt has no venues row yet; starring must create one rather than fail
        with patch("storage.Database", return_value=self.db):
            ok, _ = star_venue("kilowatt")
            self.assertTrue(ok)
            self.assertIn("Kilowatt", get_starred_venues())

    def test_numbers_match_display_order(self):
        from ui.calendar import display_order, event_numbers, numbered_calendar_events

        today = date.today()
        # Keep both events inside the calendar window (this month and next)
        self.db.save_events([self.ev("later", 0), self.ev("sooner", 0)])
        self.db.save_events(
            [
                Event(
                    date=today,
                    time=time(21, 0),
                    artists=["late"],
                    venue="The Chapel",
                    url="https://x/late",
                )
            ]
        )
        ordered = numbered_calendar_events(self.db)
        self.assertEqual(ordered, display_order(ordered))
        numbers = event_numbers(self.db)
        self.assertEqual(sorted(numbers.values()), list(range(1, len(ordered) + 1)))
        self.assertEqual(numbers[ordered[0].id], 1)
        self.assertEqual(
            ordered[0].artists_display, "late"
        )  # timed show sorts after untimed on the same day


class CliShortcutTest(unittest.TestCase):
    def test_bare_venue_name_becomes_venue_command(self):
        import cli

        parser = cli.setup_parser()
        self.assertEqual(
            cli.venue_shortcut(["great", "american"], parser),
            ["venue", "great american"],
        )
        self.assertEqual(
            cli.venue_shortcut(["kilowatt", "--force-refresh"], parser),
            ["venue", "kilowatt", "--force-refresh"],
        )
        for argv in (["pin", "5"], ["doctor"], ["--list-venues"], []):
            self.assertEqual(cli.venue_shortcut(argv, parser), argv)

    def test_tls_hint_only_for_old_openssl_403s(self):
        import cli
        from utils.parallel import VenueResult

        blocked = {
            "Rickshaw Stop": VenueResult(
                "Rickshaw Stop", "error", error="Failed to fetch x: HTTP 403"
            )
        }
        self.assertIn(
            "Rickshaw Stop", cli.tls_hint(blocked, "OpenSSL 1.1.1w  11 Sep 2023")
        )
        self.assertIsNone(cli.tls_hint(blocked, "OpenSSL 3.6.3 9 Jun 2026"))
        timeout = {"X": VenueResult("X", "error", error="Read timed out")}
        self.assertIsNone(cli.tls_hint(timeout, "OpenSSL 1.1.1w  11 Sep 2023"))


if __name__ == "__main__":
    unittest.main()
