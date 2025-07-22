#!/usr/bin/env python3
"""
Test cases for venue starring functionality
Tests star, unstar, and show starred commands before and after running music command
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
from models import Venue
import cli


class TestStarFunctionality(unittest.TestCase):
    """Test venue starring functionality"""

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
        """Set up sample venue data for testing"""
        # Add test venues
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

    def test_star_venue(self):
        """Test starring a venue"""
        venue_name = "The Warfield"

        # Verify venue starts unstarred
        starred_venues = self.db.get_starred_venues()
        self.assertNotIn(venue_name, starred_venues, "Venue should start unstarred")

        # Star the venue
        success = self.db.star_venue(venue_name)
        self.assertTrue(success, "Star operation should succeed")

        # Verify venue is starred
        starred_venues = self.db.get_starred_venues()
        self.assertIn(venue_name, starred_venues, "Venue should be starred")

    def test_unstar_venue(self):
        """Test unstarring a venue"""
        venue_name = "Great American Music Hall"

        # First star the venue
        self.db.star_venue(venue_name)
        starred_venues = self.db.get_starred_venues()
        self.assertIn(venue_name, starred_venues, "Venue should be starred")

        # Unstar the venue
        success = self.db.unstar_venue(venue_name)
        self.assertTrue(success, "Unstar operation should succeed")

        # Verify venue is unstarred
        starred_venues = self.db.get_starred_venues()
        self.assertNotIn(venue_name, starred_venues, "Venue should be unstarred")

    def test_star_multiple_venues(self):
        """Test starring multiple venues"""
        venue_names = ["The Warfield", "Rickshaw Stop", "The Independent"]

        # Star all venues
        for venue_name in venue_names:
            success = self.db.star_venue(venue_name)
            self.assertTrue(success, f"Should be able to star {venue_name}")

        # Verify all are starred
        starred_venues = self.db.get_starred_venues()
        for venue_name in venue_names:
            self.assertIn(venue_name, starred_venues, f"{venue_name} should be starred")

        self.assertEqual(len(starred_venues), 3, "Should have 3 starred venues")

    def test_star_nonexistent_venue(self):
        """Test starring a venue that doesn't exist"""
        success = self.db.star_venue("Non-existent Venue")
        self.assertFalse(success, "Should fail to star non-existent venue")

        starred_venues = self.db.get_starred_venues()
        self.assertEqual(len(starred_venues), 0, "Should have no starred venues")

    def test_star_double_star_same_venue(self):
        """Test starring the same venue twice (should be idempotent)"""
        venue_name = "The Warfield"

        # Star once
        success1 = self.db.star_venue(venue_name)
        self.assertTrue(success1, "First star should succeed")

        # Star again - should still report success (idempotent)
        success2 = self.db.star_venue(venue_name)
        self.assertTrue(success2, "Second star should succeed")

        # Should still only appear once in starred venues
        starred_venues = self.db.get_starred_venues()
        self.assertEqual(
            starred_venues.count(venue_name), 1, "Should appear exactly once"
        )
        self.assertEqual(len(starred_venues), 1, "Should have exactly 1 starred venue")

    def test_get_starred_venues_empty(self):
        """Test getting starred venues when none are starred"""
        starred_venues = self.db.get_starred_venues()
        self.assertEqual(
            len(starred_venues), 0, "Should have no starred venues initially"
        )
        self.assertIsInstance(starred_venues, list, "Should return a list")

    def test_get_starred_venues_sorted(self):
        """Test that starred venues are returned in sorted order"""
        venue_names = ["Zebra Venue", "Alpha Venue", "Beta Venue"]

        # Add these venues to database
        with self.db.get_connection() as conn:
            for venue_name in venue_names:
                conn.execute(
                    "INSERT INTO venues (name, base_url, calendar_path, starred) VALUES (?, ?, ?, ?)",
                    (venue_name, "https://test.com", "/calendar/", False),
                )

        # Star them in random order
        for venue_name in venue_names:
            self.db.star_venue(venue_name)

        # Verify they're returned sorted
        starred_venues = self.db.get_starred_venues()
        expected_order = ["Alpha Venue", "Beta Venue", "Zebra Venue"]
        self.assertEqual(
            starred_venues,
            expected_order,
            "Starred venues should be sorted alphabetically",
        )

    @patch("sys.stdout", new_callable=StringIO)
    def test_cli_star_venue_command(self, mock_stdout):
        """Test CLI star venue command"""
        venue_name = "The Warfield"

        with patch("cli.Database", return_value=self.db):
            with patch("cli.find_venue_by_fuzzy_name", return_value=venue_name):
                with patch(
                    "cli.star_venue", return_value=(True, f"Starred {venue_name}")
                ):
                    cli.handle_star_venue_command("warfield")

                    output = mock_stdout.getvalue()
                    self.assertIn("⭐", output, "Should show star emoji in output")

    @patch("sys.stdout", new_callable=StringIO)
    def test_cli_unstar_venue_command(self, mock_stdout):
        """Test CLI unstar venue command"""
        venue_name = "The Warfield"

        # First star the venue
        self.db.star_venue(venue_name)

        with patch("cli.Database", return_value=self.db):
            with patch("cli.find_venue_by_fuzzy_name", return_value=venue_name):
                with patch(
                    "cli.unstar_venue", return_value=(True, f"Unstarred {venue_name}")
                ):
                    cli.handle_unstar_venue_command("warfield")

                    output = mock_stdout.getvalue()
                    self.assertIn("⭐", output, "Should show star emoji in output")

    @patch("sys.stdout", new_callable=StringIO)
    def test_cli_show_starred_venues_empty(self, mock_stdout):
        """Test showing starred venues when none exist"""
        with patch("cli.Database", return_value=self.db):
            cli.show_starred_venues()

            output = mock_stdout.getvalue()
            self.assertIn("No venues are currently starred", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_cli_show_starred_venues_with_venues(self, mock_stdout):
        """Test showing starred venues when they exist"""
        # Star some venues first
        venues_to_star = ["The Warfield", "Rickshaw Stop"]
        for venue in venues_to_star:
            self.db.star_venue(venue)

        with patch("cli.Database", return_value=self.db):
            cli.show_starred_venues()

            output = mock_stdout.getvalue()
            self.assertIn("⭐ Starred Venues:", output)
            for venue in venues_to_star:
                self.assertIn(venue, output)

    def test_star_persistence_after_venue_update(self):
        """Test that stars persist when venue information is updated"""
        venue_name = "The Warfield"

        # Star the venue
        self.db.star_venue(venue_name)
        starred_before = self.db.get_starred_venues()
        self.assertIn(venue_name, starred_before)

        # Update venue information (simulating a config update)
        venue_obj = Venue(
            name=venue_name,
            base_url="https://updated-warfield.com",  # Changed URL
            calendar_path="/updated-calendar/",  # Changed path
        )
        self.db.save_venue(venue_obj)

        # Verify star status is preserved
        starred_after = self.db.get_starred_venues()
        self.assertIn(
            venue_name, starred_after, "Star status should persist after venue update"
        )

    def test_star_venue_case_sensitivity(self):
        """Test that venue starring is case-sensitive in database but CLI handles fuzzy matching"""
        venue_name = "The Warfield"

        # Direct database calls should be case-sensitive
        success = self.db.star_venue(venue_name)
        self.assertTrue(success)

        # Different case should fail at database level
        success_wrong_case = self.db.star_venue("the warfield")
        self.assertFalse(success_wrong_case, "Database should be case-sensitive")

        # But starred venues should still only show the correct case
        starred_venues = self.db.get_starred_venues()
        self.assertEqual(len(starred_venues), 1)
        self.assertIn(venue_name, starred_venues)

    @patch("sys.stdout", new_callable=StringIO)
    def test_cli_star_venue_fuzzy_matching(self, mock_stdout):
        """Test that CLI star command handles fuzzy matching"""
        with patch("cli.Database", return_value=self.db):
            with patch("cli.find_venue_by_fuzzy_name") as mock_fuzzy:
                mock_fuzzy.return_value = None  # No match found

                cli.handle_star_venue_command("nonexistent")

                output = mock_stdout.getvalue()
                self.assertIn("❌ No venue found", output)
                self.assertIn("Available venues:", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_cli_star_venue_multiple_matches(self, mock_stdout):
        """Test CLI behavior with multiple fuzzy matches"""
        with patch("cli.Database", return_value=self.db):
            with patch("cli.find_venue_by_fuzzy_name") as mock_fuzzy:
                mock_fuzzy.return_value = [
                    "The Independent",
                    "The Warfield",
                ]  # Multiple matches

                cli.handle_star_venue_command("the")

                output = mock_stdout.getvalue()
                self.assertIn("🔍 Multiple venues found", output)
                self.assertIn("Be more specific", output)


if __name__ == "__main__":
    unittest.main()
