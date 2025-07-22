#!/usr/bin/env python3
"""
Integration tests for pin and star functionality
Tests that pin/star work before and after running the main music command
"""

import unittest
import sys
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from io import StringIO
from datetime import date, time

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from storage.database import Database
from models import Event, Venue
import cli


class TestPinStarIntegration(unittest.TestCase):
    """Integration tests for pin and star functionality with main music command"""

    def setUp(self):
        """Set up test with temporary database"""
        # Create temporary directory for test database
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = os.path.join(self.temp_dir, "test_musiclist.db")

        # Create test database and add sample data
        self.db = Database(db_path=self.test_db_path)
        self._setup_sample_data()

    def tearDown(self):
        """Clean up after tests"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _setup_sample_data(self):
        """Set up sample venue and event data for testing"""
        # Add test venues matching some real venue names for integration
        venues = [
            ("The Warfield", "https://thewarfield.com", "/calendar/"),
            ("Great American Music Hall", "https://gamh.com", "/calendar/"),
            ("Rickshaw Stop", "https://rickshawstop.com", "/calendar/"),
            ("The Independent", "https://theindependent.com", "/calendar/"),
        ]

        with self.db.get_connection() as conn:
            for venue_data in venues:
                conn.execute(
                    "INSERT INTO venues (name, base_url, calendar_path, starred) VALUES (?, ?, ?, ?)",
                    (venue_data[0], venue_data[1], venue_data[2], False),
                )

            # Add test events for each venue (using future dates)
            from datetime import datetime, timedelta

            today = datetime.now().date()

            conn.execute(
                """INSERT INTO events (venue_id, date, time, artists, url, cost, pinned)
                VALUES (1, ?, ?, ?, ?, ?, ?)""",
                (
                    (today + timedelta(days=5)).isoformat(),
                    time(20, 0).isoformat(),
                    "Test Artist 1",
                    "https://thewarfield.com/event1",
                    "$25",
                    False,
                ),
            )
            conn.execute(
                """INSERT INTO events (venue_id, date, time, artists, url, cost, pinned)
                VALUES (2, ?, ?, ?, ?, ?, ?)""",
                (
                    (today + timedelta(days=8)).isoformat(),
                    time(19, 30).isoformat(),
                    "Test Artist 2",
                    "https://gamh.com/event1",
                    "$30",
                    False,
                ),
            )
            conn.execute(
                """INSERT INTO events (venue_id, date, time, artists, url, cost, pinned)
                VALUES (3, ?, ?, ?, ?, ?, ?)""",
                (
                    (today + timedelta(days=12)).isoformat(),
                    time(21, 0).isoformat(),
                    "Test Artist 3",
                    "https://rickshawstop.com/event1",
                    "$15",
                    False,
                ),
            )

    def _mock_scraper_response(self):
        """Mock scraper to return additional events (simulating fresh scrape)"""
        from datetime import datetime, timedelta

        today = datetime.now().date()

        # Return new events that would come from a fresh scrape
        return [
            Event(
                date=today + timedelta(days=25),
                time=time(20, 30),
                artists=["New Artist 1"],
                venue="The Warfield",
                url="https://thewarfield.com/new-event1",
                cost="$35",
            ),
            Event(
                date=today + timedelta(days=28),
                time=time(19, 0),
                artists=["New Artist 2"],
                venue="Great American Music Hall",
                url="https://gamh.com/new-event1",
                cost="$40",
            ),
        ]

    def test_pin_before_and_after_music_command(self):
        """Test that pins persist before and after running music command"""
        # STEP 1: Pin an event before music command
        events = self.db.get_recent_events()
        self.assertGreater(len(events), 0, "Should have initial test events")

        # Pin the first event
        test_event = events[0]
        success = self.db.pin_event(test_event.id)
        self.assertTrue(success, "Should be able to pin event")

        # Verify event is pinned
        pinned_before = self.db.get_pinned_events()
        self.assertEqual(
            len(pinned_before), 1, "Should have 1 pinned event before music"
        )
        self.assertEqual(
            pinned_before[0].id, test_event.id, "Pinned event should match"
        )

        # STEP 2: Simulate running music command (which scrapes and updates database)
        # Mock the scraping process to add new events
        mock_events = self._mock_scraper_response()

        # Simulate saving new events (this is what happens during music command)
        for event in mock_events:
            venue_id = self.db.get_venue_id(event.venue)
            if venue_id:
                # Simulate the event saving process
                with self.db.get_connection() as conn:
                    conn.execute(
                        """INSERT OR IGNORE INTO events (venue_id, date, time, artists, url, cost, pinned)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            venue_id,
                            event.date.isoformat(),
                            event.time.isoformat() if event.time else None,
                            event.artists_display,
                            event.url,
                            event.cost,
                            False,  # New events start unpinned
                        ),
                    )

        # STEP 3: Verify pins persist after music command
        pinned_after = self.db.get_pinned_events()
        self.assertEqual(
            len(pinned_after), 1, "Should still have 1 pinned event after music"
        )
        self.assertEqual(
            pinned_after[0].id, test_event.id, "Original pinned event should remain"
        )

        # Verify new events were added but are unpinned
        all_events_after = self.db.get_recent_events()
        self.assertGreater(
            len(all_events_after), len(events), "Should have more events after scrape"
        )

    def test_star_before_and_after_music_command(self):
        """Test that venue stars persist before and after running music command"""
        # STEP 1: Star venues before music command
        venues_to_star = ["The Warfield", "Rickshaw Stop"]

        for venue_name in venues_to_star:
            success = self.db.star_venue(venue_name)
            self.assertTrue(success, f"Should be able to star {venue_name}")

        # Verify venues are starred
        starred_before = self.db.get_starred_venues()
        self.assertEqual(
            len(starred_before), 2, "Should have 2 starred venues before music"
        )
        for venue_name in venues_to_star:
            self.assertIn(venue_name, starred_before, f"{venue_name} should be starred")

        # STEP 2: Simulate running music command with venue updates
        # This simulates what happens when venues are re-saved during scraping
        for venue_name in venues_to_star:
            venue_obj = Venue(
                name=venue_name,
                base_url="https://updated-"
                + venue_name.lower().replace(" ", "")
                + ".com",
                calendar_path="/updated-calendar/",
            )
            self.db.save_venue(venue_obj)

        # STEP 3: Verify stars persist after music command
        starred_after = self.db.get_starred_venues()
        self.assertEqual(
            len(starred_after), 2, "Should still have 2 starred venues after music"
        )
        for venue_name in venues_to_star:
            self.assertIn(
                venue_name, starred_after, f"{venue_name} should still be starred"
            )

    def test_combined_pin_and_star_integration(self):
        """Test pins and stars working together before and after music command"""
        # STEP 1: Set up pins and stars before music command

        # Star some venues
        venues_to_star = ["The Warfield", "Great American Music Hall"]
        for venue_name in venues_to_star:
            self.db.star_venue(venue_name)

        # Pin some events (preferably from starred venues)
        events = self.db.get_recent_events()
        events_to_pin = [e for e in events if e.venue in venues_to_star][:2]

        for event in events_to_pin:
            self.db.pin_event(event.id)

        # Verify initial state
        starred_before = self.db.get_starred_venues()
        pinned_before = self.db.get_pinned_events()

        self.assertEqual(len(starred_before), 2, "Should have 2 starred venues")
        self.assertEqual(len(pinned_before), 2, "Should have 2 pinned events")

        # STEP 2: Simulate full music command (venue updates + new events)

        # Update venues (as would happen during scraping)
        for venue_name in venues_to_star:
            venue_obj = Venue(
                name=venue_name,
                base_url="https://refreshed-"
                + venue_name.lower().replace(" ", "")
                + ".com",
                calendar_path="/refreshed-calendar/",
            )
            self.db.save_venue(venue_obj)

        # Add new events (as would happen during scraping)
        mock_events = self._mock_scraper_response()
        for event in mock_events:
            venue_id = self.db.get_venue_id(event.venue)
            if venue_id:
                with self.db.get_connection() as conn:
                    conn.execute(
                        """INSERT OR IGNORE INTO events (venue_id, date, time, artists, url, cost, pinned)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            venue_id,
                            event.date.isoformat(),
                            event.time.isoformat() if event.time else None,
                            event.artists_display,
                            event.url,
                            event.cost,
                            False,
                        ),
                    )

        # STEP 3: Verify both pins and stars persist
        starred_after = self.db.get_starred_venues()
        pinned_after = self.db.get_pinned_events()

        self.assertEqual(
            len(starred_after), 2, "Should still have 2 starred venues after music"
        )
        self.assertEqual(
            len(pinned_after), 2, "Should still have 2 pinned events after music"
        )

        # Verify the specific venues and events are still starred/pinned
        for venue_name in venues_to_star:
            self.assertIn(
                venue_name, starred_after, f"{venue_name} should still be starred"
            )

        pinned_ids_after = {e.id for e in pinned_after}
        expected_pinned_ids = {e.id for e in events_to_pin}
        self.assertEqual(
            pinned_ids_after, expected_pinned_ids, "Same events should remain pinned"
        )

    @patch("sys.stdout", new_callable=StringIO)
    def test_cli_integration_workflow(self, mock_stdout):
        """Test a realistic workflow using CLI commands"""
        with patch("cli.Database", return_value=self.db):
            # STEP 1: List available venues
            with patch(
                "cli.get_venue_names",
                return_value=["The Warfield", "Rickshaw Stop", "The Independent"],
            ):
                cli.list_venues()
                output1 = mock_stdout.getvalue()
                self.assertIn("🎵 Available Venues:", output1)

            mock_stdout.truncate(0)
            mock_stdout.seek(0)

            # STEP 2: Star a venue
            with patch("cli.find_venue_by_fuzzy_name", return_value="The Warfield"):
                with patch(
                    "cli.star_venue", return_value=(True, "Starred The Warfield")
                ):
                    cli.handle_star_venue_command("warfield")
                    output2 = mock_stdout.getvalue()
                    self.assertIn("⭐", output2)

            mock_stdout.truncate(0)
            mock_stdout.seek(0)

            # STEP 3: Pin an event
            with patch("cli.get_event_by_number") as mock_get_event:
                events = self.db.get_recent_events()
                if events:
                    mock_get_event.return_value = events[0]
                    cli.handle_pin_event("1")
                    output3 = mock_stdout.getvalue()
                    self.assertIn("📌", output3)

            mock_stdout.truncate(0)
            mock_stdout.seek(0)

            # STEP 4: Show pinned events
            with patch("ui.Terminal") as mock_terminal_class:
                mock_terminal = mock_terminal_class.return_value
                cli.show_pinned_events()
                mock_terminal.display_calendar_events.assert_called_once()

            mock_stdout.truncate(0)
            mock_stdout.seek(0)

            # STEP 5: Show starred venues
            cli.show_starred_venues()
            output5 = mock_stdout.getvalue()
            # The actual starring would need to happen in the database
            # but we're testing the CLI command flow

    def test_database_integrity_after_operations(self):
        """Test that database remains consistent after pin/star operations"""
        # Perform various operations
        events = self.db.get_recent_events()

        # Pin and unpin events
        if events:
            self.db.pin_event(events[0].id)
            self.db.unpin_event(events[0].id)
            self.db.pin_event(events[0].id)  # Pin again

        # Star and unstar venues
        venues = ["The Warfield", "Rickshaw Stop"]
        for venue in venues:
            self.db.star_venue(venue)
            self.db.unstar_venue(venue)
            self.db.star_venue(venue)  # Star again

        # Verify database integrity
        with self.db.get_connection() as conn:
            # Check venues table
            venue_count = conn.execute("SELECT COUNT(*) FROM venues").fetchone()[0]
            self.assertGreater(venue_count, 0, "Should have venues in database")

            # Check events table
            event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            self.assertGreater(event_count, 0, "Should have events in database")

            # Check foreign key integrity
            orphaned_events = conn.execute(
                "SELECT COUNT(*) FROM events e LEFT JOIN venues v ON e.venue_id = v.id WHERE v.id IS NULL"
            ).fetchone()[0]
            self.assertEqual(orphaned_events, 0, "Should not have orphaned events")

    def test_edge_case_empty_database(self):
        """Test pin/star functionality with empty database"""
        # Clear the database
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM events")
            conn.execute("DELETE FROM venues")

        # Try operations on empty database
        pinned_events = self.db.get_pinned_events()
        self.assertEqual(
            len(pinned_events), 0, "Should have no pinned events in empty database"
        )

        starred_venues = self.db.get_starred_venues()
        self.assertEqual(
            len(starred_venues), 0, "Should have no starred venues in empty database"
        )

        # Try to pin non-existent event
        success = self.db.pin_event(999)
        self.assertFalse(success, "Should fail to pin non-existent event")

        # Try to star non-existent venue
        success = self.db.star_venue("Non-existent Venue")
        self.assertFalse(success, "Should fail to star non-existent venue")


if __name__ == "__main__":
    unittest.main()
