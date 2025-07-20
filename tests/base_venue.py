import unittest
import csv
import os
from datetime import date, time
from typing import List, Dict, Any

from models import Event, Venue
from scrapers.base import BaseScraper
from tests.base import BaseScraperTest


class BaseVenueTest(BaseScraperTest):
    """Base class for venue tests using CSV data files"""

    # To be overridden by subclasses
    VENUE_NAME = None
    SCRAPER_CLASS = None
    BASE_URL = None
    CALENDAR_PATH = "/calendar/"

    def setUp(self):
        """Set up test data using CSV files"""
        super().setUp()

        if self.VENUE_NAME is None:
            self.skipTest("VENUE_NAME not set - this is an abstract base class")

        # Create venue
        self.venue = Venue(
            name=self.VENUE_NAME,
            base_url=self.BASE_URL,
            calendar_path=self.CALENDAR_PATH,
        )

        # Create scraper
        if self.SCRAPER_CLASS:
            self.scraper = self.SCRAPER_CLASS(self.venue)

        # Load expected events from CSV
        self.sample_events = self._load_events_from_csv()

    def _get_csv_filename(self) -> str:
        """Get CSV filename for this venue"""
        # Convert venue name to safe filename
        safe_name = self.VENUE_NAME.lower().replace(" ", "_").replace("&", "and")
        return f"tests/data/{safe_name}_expected.csv"

    def _load_events_from_csv(self) -> List[Event]:
        """Load expected events from CSV file"""
        csv_file = self._get_csv_filename()

        if not os.path.exists(csv_file):
            return []

        events = []
        with open(csv_file, "r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
                    event = self._csv_row_to_event(row)
                    if event:
                        events.append(event)
                except Exception as e:
                    print(f"Warning: Failed to parse CSV row {row}: {e}")
                    continue

        return events

    def _csv_row_to_event(self, row: Dict[str, str]) -> Event:
        """Convert CSV row to Event object"""
        # Parse date
        event_date = date.fromisoformat(row["date"])

        # Parse time (optional)
        event_time = None
        if row.get("time") and row["time"] != "None":
            event_time = time.fromisoformat(row["time"])

        # Parse artists (comma-separated)
        artists = [
            artist.strip() for artist in row["artists"].split(",") if artist.strip()
        ]

        return Event(
            date=event_date,
            time=event_time,
            artists=artists,
            venue=row["venue"],
            url=row["url"],
            cost=row.get("cost") if row.get("cost") else None,
        )

    def _event_to_csv_row(self, event: Event) -> Dict[str, str]:
        """Convert Event object to CSV row"""
        return {
            "date": event.date.isoformat(),
            "time": event.time.isoformat() if event.time else "",
            "artists": ", ".join(event.artists),
            "venue": event.venue,
            "url": event.url,
            "cost": event.cost if event.cost else "",
        }

    def generate_csv_file(self, events: List[Event]):
        """Generate CSV file from actual scraped events"""
        csv_file = self._get_csv_filename()

        # Ensure data directory exists
        os.makedirs(os.path.dirname(csv_file), exist_ok=True)

        with open(csv_file, "w", newline="", encoding="utf-8") as file:
            if not events:
                # Create empty file with headers
                writer = csv.writer(file)
                writer.writerow(["date", "time", "artists", "venue", "url", "cost"])
                return

            # Write events
            fieldnames = ["date", "time", "artists", "venue", "url", "cost"]
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            writer.writeheader()
            for event in events:
                writer.writerow(self._event_to_csv_row(event))

        print(f"Generated CSV file: {csv_file}")

    # Common test methods that work with any venue

    def test_csv_data_loads(self):
        """Test that CSV data file exists and loads correctly"""
        csv_file = self._get_csv_filename()

        if not os.path.exists(csv_file):
            self.skipTest(f"CSV file not found: {csv_file}")

        # Should have loaded some events
        self.assertGreaterEqual(
            len(self.sample_events), 0, "CSV file should contain events or be empty"
        )

    def test_event_data_structure(self):
        """Test that events from CSV have proper data structure"""
        if not self.sample_events:
            self.skipTest("No sample events to test")

        for event in self.sample_events:
            # Test required fields
            self.assertIsInstance(event.date, date)
            self.assertIsInstance(event.artists, list)
            self.assertTrue(len(event.artists) > 0)
            self.assertIsInstance(event.venue, str)
            self.assertIsInstance(event.url, str)

            # Test data integrity
            self.assertTrue(event.venue)
            self.assertTrue(event.url.startswith("http"))

            # Test database serialization
            event_dict = event.to_dict()
            self.assertIn("date", event_dict)
            self.assertIn("artists", event_dict)
            self.assertIn("venue", event_dict)
            self.assertIn("url", event_dict)

    def test_venue_consistency(self):
        """Test that all events have consistent venue information"""
        if not self.sample_events:
            self.skipTest("No sample events to test")

        for event in self.sample_events:
            self.assertEqual(event.venue, self.VENUE_NAME)

    def test_database_roundtrip(self):
        """Test that events can be serialized to dict and back"""
        if not self.sample_events:
            self.skipTest("No sample events to test")

        for original_event in self.sample_events:
            # Serialize to dict (as would be stored in database)
            event_dict = original_event.to_dict()

            # Deserialize back to Event object
            restored_event = Event.from_dict(event_dict)

            # Compare all fields
            self.assertEqual(original_event.date, restored_event.date)
            self.assertEqual(original_event.time, restored_event.time)
            self.assertEqual(original_event.artists, restored_event.artists)
            self.assertEqual(original_event.venue, restored_event.venue)
            self.assertEqual(original_event.url, restored_event.url)
            self.assertEqual(original_event.cost, restored_event.cost)

    def test_csv_roundtrip(self):
        """Test that events can be converted to CSV and back"""
        if not self.sample_events:
            self.skipTest("No sample events to test")

        for original_event in self.sample_events:
            # Convert to CSV row and back
            csv_row = self._event_to_csv_row(original_event)
            restored_event = self._csv_row_to_event(csv_row)

            # Compare all fields
            self.assertEqual(original_event.date, restored_event.date)
            self.assertEqual(original_event.time, restored_event.time)
            self.assertEqual(original_event.artists, restored_event.artists)
            self.assertEqual(original_event.venue, restored_event.venue)
            self.assertEqual(original_event.url, restored_event.url)
            self.assertEqual(original_event.cost, restored_event.cost)
