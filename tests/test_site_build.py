"""Offline tests for site/build.py: price tidying and the events.json export."""

import importlib.util
import os
import re
import sys
import tempfile
import unittest
from datetime import date, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models import Event, Venue  # noqa: E402
from storage.database import Database  # noqa: E402
from utils.parallel import VenueResult  # noqa: E402


def load_build():
    # "site" is also a stdlib module name, so load the script by path.
    spec = importlib.util.spec_from_file_location(
        "site_build", ROOT / "site" / "build.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PriceTest(unittest.TestCase):
    def setUp(self):
        self.price = load_build().price

    def test_tidies_ranges_and_cents(self):
        self.assertEqual(self.price("$25.00 - $30.00"), "$25–$30")
        self.assertEqual(self.price("$12.33 - $47.32"), "$12.33–$47.32")
        self.assertEqual(self.price("$12-$30"), "$12–$30")
        self.assertEqual(self.price("$20 at the door"), "$20 at the door")

    def test_free_and_missing(self):
        for cost in ("$0", "$0.00", "Free", "$0 - $0"):
            self.assertEqual(self.price(cost), "free", cost)
        self.assertIsNone(self.price(None))
        self.assertIsNone(self.price("  "))


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.build = load_build()
        self.db = Database(os.path.join(self.tmp.name, "site.db"))
        self.configs = [
            {
                "name": "Alpha Hall",
                "area": "Mission",
                "base_url": "https://alpha.example/",
                "calendar_path": "/shows",
            },
            {
                "name": "Beta Room",
                "area": "Uptown",
                "kind": "club",
                "city": "Oakland",
                "base_url": "https://beta.example",
                "calendar_path": "/",
                "home_url": "https://beta.home/",
            },
        ]
        today = date.today()
        for cfg in self.configs:
            self.db.save_venue(
                Venue(cfg["name"], cfg["base_url"], cfg["calendar_path"])
            )
        # save_events stores one venue's events per call
        self.db.save_events(
            [
                Event(
                    today + timedelta(days=2),
                    time(20, 0),
                    ["Headliner", "Opener"],
                    "Alpha Hall",
                    "https://alpha.example/1",
                    "$15.00",
                )
            ]
        )
        self.db.save_events(
            [
                Event(
                    today,
                    None,
                    ["Matinee"],
                    "Beta Room",
                    "https://beta.example/2",
                    "$0.00",
                ),
                Event(
                    today - timedelta(days=1),
                    time(21, 0),
                    ["Yesterday"],
                    "Beta Room",
                    "https://beta.example/3",
                ),
            ]
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_export_shape(self):
        results = {
            "Alpha Hall": VenueResult("Alpha Hall", "fresh", 1),
            "Beta Room": VenueResult("Beta Room", "error", error="HTTP 403"),
        }
        data = self.build.export(self.configs, self.db, results)

        self.assertEqual(
            [
                (
                    v["name"],
                    v["area"],
                    v["city"],
                    v["kind"],
                    v["url"],
                    v["shows"],
                    v["stale"],
                )
                for v in data["venues"]
            ],
            [
                # no city or kind configured: San Francisco, "other"
                (
                    "Alpha Hall",
                    "Mission",
                    "San Francisco",
                    "other",
                    "https://alpha.example/shows",
                    1,
                    False,
                ),
                # home_url wins over the scraped calendar for the link
                (
                    "Beta Room",
                    "Uptown",
                    "Oakland",
                    "club",
                    "https://beta.home/",
                    1,
                    True,
                ),
            ],
        )
        # past shows are left out; events point at venues by index, in date order
        self.assertEqual(
            [e["artists"] for e in data["events"]],
            [["Matinee"], ["Headliner", "Opener"]],
        )
        matinee, headliner = data["events"]
        self.assertEqual(
            (matinee["venue"], matinee["time"], matinee["price"]), (1, None, "free")
        )
        self.assertEqual(
            (headliner["venue"], headliner["time"], headliner["price"]),
            (0, "20:00", "$15"),
        )

    def test_no_scrape_marks_nothing_stale(self):
        data = self.build.export(self.configs, self.db, {})
        self.assertFalse(any(v["stale"] for v in data["venues"]))


class VenueConfigTest(unittest.TestCase):
    def test_every_venue_has_a_known_kind_and_city(self):
        from venues_config import CITIES, DEFAULT_CITY, VENUE_KINDS, get_venues_config

        for cfg in get_venues_config():
            self.assertIn(cfg.get("kind"), VENUE_KINDS, cfg["name"])
            self.assertIn(cfg.get("city", DEFAULT_CITY), CITIES, cfg["name"])

    def test_kind_labels_match_the_page(self):
        from venues_config import VENUE_KINDS

        app = (ROOT / "site" / "public" / "app.js").read_text(encoding="utf-8")
        block = app[
            app.index("const KINDS = {") : app.index("};", app.index("const KINDS = {"))
        ]

        self.assertEqual(re.findall(r"(\w+):\s*\"", block), VENUE_KINDS)


if __name__ == "__main__":
    unittest.main()
