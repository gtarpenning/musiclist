# TEMPLATE: Copy this file to test_[venue_name].py and modify as needed
#
# Example: test_warfield.py, test_fillmore.py, etc.
#
# This is now EXTREMELY simple - just set 4 class variables!

import unittest
from scrapers.your_venue_scraper import YourVenueScraper  # Replace with actual scraper
from tests.base_venue import BaseVenueTest


class TestYourVenueScraper(BaseVenueTest):  # Replace YourVenue with actual venue name
    """Test cases for Your Venue Name scraper - data-driven from CSV"""  # Replace with actual venue name

    # ALL CONFIGURATION NEEDED - JUST THESE 4 LINES!
    VENUE_NAME = "Your Venue Name"  # Replace with actual name
    SCRAPER_CLASS = YourVenueScraper  # Replace with actual scraper class
    BASE_URL = "https://venue-website.com"  # Replace with actual URL
    CALENDAR_PATH = "/events/"  # Replace with actual calendar path (optional, defaults to "/calendar/")

    # That's it! All test methods are inherited from BaseVenueTest:
    # - test_csv_data_loads()
    # - test_event_data_structure()
    # - test_venue_consistency()
    # - test_database_roundtrip()
    # - test_csv_roundtrip()
    # Plus inherited from BaseScraperTest:
    # - test_venue_setup()
    # - test_scraper_initialization()


# INSTRUCTIONS FOR USING THIS TEMPLATE:
#
# 1. Copy this file to tests/test_[venue_name].py
# 2. Replace "YourVenue" with the actual venue name throughout
# 3. Import the correct scraper class
# 4. Update the 4 class variables (VENUE_NAME, SCRAPER_CLASS, BASE_URL, CALENDAR_PATH)
# 5. Generate CSV file: python tests/run_tests.py [venue_name] --generate
# 6. Run tests: python tests/run_tests.py [venue_name]
#
# THAT'S IT! No manual event data, no complex test methods.
#
# The CSV file (tests/data/[venue_name]_expected.csv) contains the expected output.
# To regenerate it from actual scraping: python tests/run_tests.py [venue_name] --generate
#
# Available commands:
# - python tests/run_tests.py venue_name                    # Run all tests for venue
# - python tests/run_tests.py venue_name --generate         # Generate CSV from scraper
# - python tests/run_tests.py venue_name test_csv_roundtrip # Run specific test method


if __name__ == "__main__":
    unittest.main()
