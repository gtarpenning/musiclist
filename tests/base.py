import unittest
from datetime import date, time
from typing import List

from models import Event, Venue
from scrapers.base import BaseScraper


class BaseScraperTest(unittest.TestCase):
    """Base test class for venue scrapers with common utilities"""

    def setUp(self):
        """Set up common test data"""
        self.venue = None  # To be set by subclasses
        self.scraper = None  # To be set by subclasses
        self.sample_events = []  # To be set by subclasses

    def __init_subclass__(cls, **kwargs):
        """Ensure only concrete test classes run tests"""
        super().__init_subclass__(**kwargs)
        # Skip base class tests
        if cls.__name__ == "BaseScraperTest":
            cls.setUp = None

    def assertEventEqual(self, actual: Event, expected: Event):
        """Compare two events, handling time comparison carefully"""
        self.assertEqual(actual.date, expected.date)
        self.assertEqual(actual.time, expected.time)
        self.assertEqual(actual.artists, expected.artists)
        self.assertEqual(actual.venue, expected.venue)
        self.assertEqual(actual.url, expected.url)
        self.assertEqual(actual.cost, expected.cost)

    def assertEventsMatch(
        self, actual_events: List[Event], expected_events: List[Event]
    ):
        """Compare two lists of events"""
        self.assertEqual(len(actual_events), len(expected_events))
        for actual, expected in zip(actual_events, expected_events):
            self.assertEventEqual(actual, expected)

    def test_venue_setup(self):
        """Test that venue is properly configured - only for concrete subclasses"""
        if self.__class__ == BaseScraperTest:
            self.skipTest("Base class test")

        self.assertIsNotNone(self.venue)
        self.assertIsInstance(self.venue, Venue)
        self.assertTrue(self.venue.name)
        self.assertTrue(self.venue.base_url)
        self.assertTrue(self.venue.calendar_path)

    def test_scraper_initialization(self):
        """Test that scraper is properly initialized - only for concrete subclasses"""
        if self.__class__ == BaseScraperTest:
            self.skipTest("Base class test")

        self.assertIsNotNone(self.scraper)
        self.assertIsInstance(self.scraper, BaseScraper)
        self.assertEqual(self.scraper.venue, self.venue)
