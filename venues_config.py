#!/usr/bin/env python3
"""
Centralized venue configuration for the musiclist project.

This configuration is used by:
- main.py and music_calendar.py for scraping
- Test framework for automatic test generation
- CLI for venue selection
"""

from scrapers.brick_mortar import BrickMortarScraper
from scrapers.warfield import WarfieldScraper

# All venue configurations
VENUES_CONFIG = [
    {
        "name": "Brick & Mortar Music Hall",
        "base_url": "https://www.brickandmortarmusic.com",
        "calendar_path": "/calendar/",
        "scraper_class": BrickMortarScraper,
        "enabled": True,
    },
    {
        "name": "The Warfield", 
        "base_url": "https://www.thewarfieldtheatre.com",
        "calendar_path": "/events/",
        "scraper_class": WarfieldScraper,
        "enabled": True,
    },
    # Future venues can be added here
    # {
    #     "name": "Great American Music Hall",
    #     "base_url": "https://gamh.com",
    #     "calendar_path": "/calendar/",
    #     "scraper_class": GAMHScraper,
    #     "enabled": False,  # Not implemented yet
    # },
]


def get_enabled_venues():
    """Get list of enabled venue configurations"""
    return [venue for venue in VENUES_CONFIG if venue.get("enabled", True)]


def get_venue_by_name(name: str):
    """Get venue configuration by name"""
    name_lower = name.lower()
    for venue in VENUES_CONFIG:
        if venue["name"].lower() == name_lower:
            return venue
    return None


def get_venue_names():
    """Get list of all venue names"""
    return [venue["name"] for venue in VENUES_CONFIG]


def get_enabled_venue_names():
    """Get list of enabled venue names"""
    return [venue["name"] for venue in get_enabled_venues()]


def venue_to_legacy_format(venue_config):
    """Convert new config format to legacy format for backward compatibility"""
    return {
        "venue_data": {
            "name": venue_config["name"],
            "base_url": venue_config["base_url"],
            "calendar_path": venue_config["calendar_path"],
        },
        "scraper_class": venue_config["scraper_class"],
    }


# For backward compatibility, provide the legacy format
def get_legacy_venues_config():
    """Get venues in legacy format for existing code"""
    return [venue_to_legacy_format(venue) for venue in get_enabled_venues()] 