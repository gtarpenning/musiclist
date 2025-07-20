#!/usr/bin/env python3
"""
Centralized venue configuration for the musiclist project.

This configuration is used by:
- main.py and music_calendar.py for scraping
- Test framework for automatic test generation
- CLI for venue selection
"""

import json
import os
from scrapers.brick_mortar import BrickMortarScraper
from scrapers.warfield import WarfieldScraper

# Configuration file for storing user preferences
USER_CONFIG_FILE = "user_config.json"

# All venue configurations
VENUES_CONFIG = [
    {
        "name": "Brick & Mortar Music Hall",
        "base_url": "https://www.brickandmortarmusic.com",
        "calendar_path": "/calendar/",
        "scraper_class": BrickMortarScraper,
        "enabled": True,
        "starred": False,
    },
    {
        "name": "The Warfield",
        "base_url": "https://www.thewarfieldtheatre.com",
        "calendar_path": "/events/",
        "scraper_class": WarfieldScraper,
        "enabled": True,
        "starred": False,
    },
    # Future venues can be added here
    # {
    #     "name": "Great American Music Hall",
    #     "base_url": "https://gamh.com",
    #     "calendar_path": "/calendar/",
    #     "scraper_class": GAMHScraper,
    #     "enabled": False,  # Not implemented yet
    #     "starred": False,
    # },
]


def _load_user_config():
    """Load user configuration from JSON file"""
    if os.path.exists(USER_CONFIG_FILE):
        try:
            with open(USER_CONFIG_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_user_config(config):
    """Save user configuration to JSON file"""
    try:
        with open(USER_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except IOError:
        pass  # Fail silently if we can't save


def _get_venue_starred_status(venue_name):
    """Get the starred status for a venue from user config"""
    config = _load_user_config()
    starred_venues = config.get("starred_venues", [])
    return venue_name in starred_venues


def get_enabled_venues():
    """Get list of enabled venue configurations with starred status from user config"""
    venues = []
    for venue in VENUES_CONFIG:
        if venue.get("enabled", True):
            venue_copy = venue.copy()
            venue_copy["starred"] = _get_venue_starred_status(venue["name"])
            venues.append(venue_copy)
    return venues


def get_venue_by_name(name: str):
    """Get venue configuration by name with starred status"""
    name_lower = name.lower()
    for venue in VENUES_CONFIG:
        if venue["name"].lower() == name_lower:
            venue_copy = venue.copy()
            venue_copy["starred"] = _get_venue_starred_status(venue["name"])
            return venue_copy
    return None


def star_venue(venue_name: str):
    """Star a venue"""
    venue = get_venue_by_name(venue_name)
    if not venue:
        return False, f"Venue '{venue_name}' not found"

    config = _load_user_config()
    starred_venues = config.get("starred_venues", [])

    if venue["name"] not in starred_venues:
        starred_venues.append(venue["name"])
        config["starred_venues"] = starred_venues
        _save_user_config(config)
        return True, f"Starred '{venue['name']}'"
    else:
        return True, f"'{venue['name']}' is already starred"


def unstar_venue(venue_name: str):
    """Unstar a venue"""
    venue = get_venue_by_name(venue_name)
    if not venue:
        return False, f"Venue '{venue_name}' not found"

    config = _load_user_config()
    starred_venues = config.get("starred_venues", [])

    if venue["name"] in starred_venues:
        starred_venues.remove(venue["name"])
        config["starred_venues"] = starred_venues
        _save_user_config(config)
        return True, f"Unstarred '{venue['name']}'"
    else:
        return True, f"'{venue['name']}' was not starred"


def get_starred_venues():
    """Get list of starred venue names"""
    config = _load_user_config()
    return config.get("starred_venues", [])


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
