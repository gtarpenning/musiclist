#!/usr/bin/env python3
"""
Test cases for event pinning functionality
Tests pin, unpin, and show pinned commands before and after running music command
"""

import unittest
import sys
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from io import StringIO

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from storage.database import Database
from models import Event
from datetime import date, time
import cli


class TestPinFunctionality(unittest.TestCase):
    """Test event pinning functionality"""

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
        # Add test venues
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO venues (name, base_url, calendar_path) VALUES (?, ?, ?)",
                ("Test Venue 1", "https://test1.com", "/calendar/"),
            )
            conn.execute(
                "INSERT INTO venues (name, base_url, calendar_path) VALUES (?, ?, ?)",
                ("Test Venue 2", "https://test2.com", "/calendar/"),
            )

            # Add test events (using future dates)
            from datetime import datetime, timedelta

            today = datetime.now().date()

            conn.execute(
                """INSERT INTO events (venue_id, date, time, artists, url, cost, pinned)
                VALUES (1, ?, ?, ?, ?, ?, ?)""",
                (
                    (today + timedelta(days=5)).isoformat(),
                    time(20, 0).isoformat(),
                    "Test Artist 1",
                    "https://test1.com/event1",
                    "$20",
                    False,
                ),
            )
            conn.execute(
                """INSERT INTO events (venue_id, date, time, artists, url, cost, pinned)
                VALUES (1, ?, ?, ?, ?, ?, ?)""",
                (
                    (today + timedelta(days=10)).isoformat(),
                    time(19, 30).isoformat(),
                    "Test Artist 2",
                    "https://test1.com/event2",
                    "$25",
                    False,
                ),
            )
            conn.execute(
                """INSERT INTO events (venue_id, date, time, artists, url, cost, pinned)
                VALUES (2, ?, ?, ?, ?, ?, ?)""",
                (
                    (today + timedelta(days=15)).isoformat(),
                    time(21, 0).isoformat(),
                    "Test Artist 3",
                    "https://test2.com/event3",
                    "$30",
                    False,
                ),
            )

    def test_pin_by_event_id(self):
        """Test pinning an event by database ID"""
        # Get an event ID
        events = self.db.get_recent_events()
        self.assertGreater(len(events), 0, "Should have test events")

        test_event = events[0]
        self.assertFalse(test_event.pinned, "Event should start unpinned")

        # Pin the event
        success = self.db.pin_event(test_event.id)
        self.assertTrue(success, "Pin operation should succeed")

        # Verify event is pinned
        pinned_events = self.db.get_pinned_events()
        self.assertEqual(len(pinned_events), 1, "Should have 1 pinned event")
        self.assertEqual(
            pinned_events[0].id, test_event.id, "Pinned event should match"
        )
        self.assertTrue(pinned_events[0].pinned, "Event should be marked as pinned")

    def test_unpin_event(self):
        """Test unpinning an event"""
        # First pin an event
        events = self.db.get_recent_events()
        test_event = events[0]
        self.db.pin_event(test_event.id)

        # Verify it's pinned
        pinned_events = self.db.get_pinned_events()
        self.assertEqual(len(pinned_events), 1, "Should have 1 pinned event")

        # Unpin the event
        success = self.db.unpin_event(test_event.id)
        self.assertTrue(success, "Unpin operation should succeed")

        # Verify it's unpinned
        pinned_events = self.db.get_pinned_events()
        self.assertEqual(len(pinned_events), 0, "Should have 0 pinned events")

    def test_multiple_pins(self):
        """Test pinning multiple events"""
        events = self.db.get_recent_events()
        self.assertGreaterEqual(len(events), 2, "Need at least 2 test events")

        # Pin first two events
        self.db.pin_event(events[0].id)
        self.db.pin_event(events[1].id)

        # Verify both are pinned
        pinned_events = self.db.get_pinned_events()
        self.assertEqual(len(pinned_events), 2, "Should have 2 pinned events")

        pinned_ids = {event.id for event in pinned_events}
        expected_ids = {events[0].id, events[1].id}
        self.assertEqual(pinned_ids, expected_ids, "Pinned events should match")

    def test_pin_nonexistent_event(self):
        """Test pinning a non-existent event ID"""
        # Try to pin event with ID that doesn't exist
        success = self.db.pin_event(999999)
        self.assertFalse(success, "Pin operation should fail for non-existent ID")

        # Verify no events are pinned
        pinned_events = self.db.get_pinned_events()
        self.assertEqual(len(pinned_events), 0, "Should have 0 pinned events")

    def test_pin_persistence_after_new_events(self):
        """Test that pins persist when new events are added"""
        # Pin an event
        events = self.db.get_recent_events()
        test_event = events[0]
        self.db.pin_event(test_event.id)

        # Verify it's pinned
        pinned_before = self.db.get_pinned_events()
        self.assertEqual(len(pinned_before), 1, "Should have 1 pinned event")

        # Add a new event (simulating a scrape update)
        with self.db.get_connection() as conn:
            from datetime import datetime, timedelta

            today = datetime.now().date()
            conn.execute(
                """INSERT INTO events (venue_id, date, time, artists, url, cost, pinned)
                VALUES (1, ?, ?, ?, ?, ?, ?)""",
                (
                    (today + timedelta(days=20)).isoformat(),
                    time(20, 0).isoformat(),
                    "New Artist",
                    "https://test1.com/new-event",
                    "$35",
                    False,
                ),
            )

        # Verify original pin still exists
        pinned_after = self.db.get_pinned_events()
        self.assertEqual(len(pinned_after), 1, "Should still have 1 pinned event")
        self.assertEqual(
            pinned_after[0].id, test_event.id, "Original pinned event should remain"
        )

    @patch("sys.stdout", new_callable=StringIO)
    def test_cli_pin_command(self, mock_stdout):
        """Test CLI pin command functionality"""
        # Mock the CLI functions to use our test database
        with patch("cli.Database", return_value=self.db):
            with patch("cli.get_event_by_number") as mock_get_event:
                # Mock getting an event by number
                events = self.db.get_recent_events()
                test_event = events[0]
                mock_get_event.return_value = test_event

                # Test pin command
                cli.handle_pin_event("1")

                # Verify output
                output = mock_stdout.getvalue()
                self.assertIn("📌 Pinned event", output)

                # Verify event is actually pinned in database
                pinned_events = self.db.get_pinned_events()
                self.assertEqual(len(pinned_events), 1)

    @patch("sys.stdout", new_callable=StringIO)
    def test_cli_unpin_command(self, mock_stdout):
        """Test CLI unpin command functionality"""
        # First pin an event
        events = self.db.get_recent_events()
        test_event = events[0]
        self.db.pin_event(test_event.id)

        # Get the updated pinned event from database
        pinned_events = self.db.get_pinned_events()
        pinned_event = pinned_events[0]

        with patch("cli.Database", return_value=self.db):
            with patch("cli.get_event_by_number") as mock_get_event:
                mock_get_event.return_value = pinned_event  # Return the pinned version

                # Test unpin command
                cli.handle_unpin_event("1")

                # Verify output
                output = mock_stdout.getvalue()
                self.assertIn("📌 Unpinned event", output)

                # Verify event is actually unpinned in database
                pinned_events = self.db.get_pinned_events()
                self.assertEqual(len(pinned_events), 0)

    @patch("sys.stdout", new_callable=StringIO)
    def test_cli_show_pinned_empty(self, mock_stdout):
        """Test showing pinned events when none exist"""
        with patch("cli.Database", return_value=self.db):
            cli.show_pinned_events()

            output = mock_stdout.getvalue()
            self.assertIn("📌 No events are currently pinned", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_cli_show_pinned_with_events(self, mock_stdout):
        """Test showing pinned events when they exist"""
        # Pin an event first
        events = self.db.get_recent_events()
        self.db.pin_event(events[0].id)

        with patch("cli.Database", return_value=self.db):
            with patch("ui.Terminal") as mock_terminal_class:
                mock_terminal = mock_terminal_class.return_value

                cli.show_pinned_events()

                # Verify terminal display_calendar_events was called
                mock_terminal.display_calendar_events.assert_called_once()
                call_args = mock_terminal.display_calendar_events.call_args[0]
                displayed_events = call_args[0]
                self.assertEqual(len(displayed_events), 1)
                self.assertTrue(displayed_events[0].pinned)

    def test_pin_double_pin_same_event(self):
        """Test pinning the same event twice (should be idempotent)"""
        events = self.db.get_recent_events()
        test_event = events[0]

        # Pin once
        success1 = self.db.pin_event(test_event.id)
        self.assertTrue(success1, "First pin should succeed")

        # Pin again - should still report success (idempotent)
        success2 = self.db.pin_event(test_event.id)
        self.assertTrue(success2, "Second pin should succeed")

        # Should still only have one pinned event
        pinned_events = self.db.get_pinned_events()
        self.assertEqual(len(pinned_events), 1, "Should have exactly 1 pinned event")

    def test_toggle_pin_functionality(self):
        """Test the toggle pin functionality"""
        events = self.db.get_recent_events()
        test_event = events[0]

        # Toggle from unpinned to pinned
        new_status = self.db.toggle_pin_event(test_event.id)
        self.assertTrue(new_status, "Should return True when pinning")

        pinned_events = self.db.get_pinned_events()
        self.assertEqual(len(pinned_events), 1, "Should have 1 pinned event")

        # Toggle from pinned to unpinned
        new_status = self.db.toggle_pin_event(test_event.id)
        self.assertFalse(new_status, "Should return False when unpinning")

        pinned_events = self.db.get_pinned_events()
        self.assertEqual(len(pinned_events), 0, "Should have 0 pinned events")


if __name__ == "__main__":
    unittest.main()
