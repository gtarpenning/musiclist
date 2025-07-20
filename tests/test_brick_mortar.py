import unittest
from scrapers.brick_mortar import BrickMortarScraper
from tests.base_venue import BaseVenueTest


class TestBrickMortarScraper(BaseVenueTest):
    """Test cases for Brick & Mortar Music Hall scraper - data-driven from CSV"""

    # All configuration needed for this venue
    VENUE_NAME = "Brick & Mortar Music Hall"
    SCRAPER_CLASS = BrickMortarScraper
    BASE_URL = "https://www.brickandmortarmusic.com"
    CALENDAR_PATH = "/calendar/"


if __name__ == "__main__":
    unittest.main()
