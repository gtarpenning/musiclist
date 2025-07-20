import unittest
from scrapers.warfield import WarfieldScraper
from tests.base_venue import BaseVenueTest


class TestWarfieldScraper(BaseVenueTest):
    """Test cases for The Warfield scraper - data-driven from CSV"""

    # All configuration needed for this venue
    VENUE_NAME = "The Warfield"
    SCRAPER_CLASS = WarfieldScraper
    BASE_URL = "https://www.thewarfieldtheatre.com"
    CALENDAR_PATH = "/events/"


if __name__ == "__main__":
    unittest.main()
