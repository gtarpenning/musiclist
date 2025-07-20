#!/usr/bin/env python3
"""
Dynamic venue test generation based on centralized config.

This replaces individual test_[venue].py files by automatically creating
test classes for each venue defined in venues_config.py.
"""

import unittest
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.base_venue import BaseVenueTest
from venues_config import get_enabled_venues


def create_venue_test_class(venue_config):
    """Create a test class for a specific venue"""

    # Create safe class name from venue name
    safe_name = (
        venue_config["name"].replace(" ", "").replace("&", "And").replace("-", "")
    )
    class_name = f"Test{safe_name}Scraper"

    # Create the test class dynamically
    class_dict = {
        "__doc__": f"Test cases for {venue_config['name']} scraper - data-driven from CSV",
        "VENUE_NAME": venue_config["name"],
        "SCRAPER_CLASS": venue_config["scraper_class"],
        "BASE_URL": venue_config["base_url"],
        "CALENDAR_PATH": venue_config["calendar_path"],
    }

    # Create the class
    test_class = type(class_name, (BaseVenueTest,), class_dict)

    return test_class


def generate_all_venue_tests():
    """Generate test classes for all enabled venues"""
    venues = get_enabled_venues()
    test_classes = []

    for venue_config in venues:
        test_class = create_venue_test_class(venue_config)
        test_classes.append(test_class)

        # Add to current module's globals so unittest can find it
        globals()[test_class.__name__] = test_class

    return test_classes


# Generate all test classes when module is imported
generated_classes = generate_all_venue_tests()


if __name__ == "__main__":
    # Run all dynamically generated tests
    unittest.main()
