#!/usr/bin/env python3
"""
Centralized venue configuration for the musiclist project.

This configuration is used by:
- cli.py for scraping and calendar display
- Test framework for automatic test generation
- CLI for venue selection
"""

# Parallelism configuration
DEFAULT_MAX_WORKERS = 5  # Number of venues to scrape in parallel

from scrapers.brick_mortar import BrickMortarScraper
from scrapers.warfield import WarfieldScraper
from scrapers.gamh import GAMHScraper
from scrapers.neck_woods import NeckOfTheWoodsScraper
from scrapers.regency_ballroom import RegencyBallroomScraper
from scrapers.midway import MidwayScraper
from scrapers.independent import IndependentScraper
from scrapers.bottom_of_hill import BottomOfTheHillScraper
from scrapers.audio_nightclub import AudioNightclubScraper
from scrapers.reverb import ReverbScraper
from scrapers.public_works import PublicWorksScraper
from scrapers.rickshaw_stop import RickshawStopScraper
from scrapers.bimbos_365 import Bimbos365Scraper
from scrapers.gray_area import GrayAreaScraper
from scrapers.chapel import ChapelScraper


# All venue configurations
VENUES_CONFIG = [
    {
        "name": "Brick & Mortar Music Hall",
        "base_url": "https://www.brickandmortarmusic.com",
        "calendar_path": "/calendar/",
        "scraper_class": BrickMortarScraper,
    },
    {
        "name": "The Warfield",
        "base_url": "https://www.thewarfieldtheatre.com",
        "calendar_path": "/events/",
        "scraper_class": WarfieldScraper,
    },
    {
        "name": "Great American Music Hall",
        "base_url": "https://gamh.com",
        "calendar_path": "/calendar/",
        "scraper_class": GAMHScraper,
    },
    {
        "name": "Neck of the Woods",
        "base_url": "https://www.neckofthewoodssf.com",
        "calendar_path": "/calendar/",
        "scraper_class": NeckOfTheWoodsScraper,
    },
    {
        "name": "The Regency Ballroom",
        "base_url": "https://www.theregencyballroom.com",
        "calendar_path": "/shows/",
        "scraper_class": RegencyBallroomScraper,
    },
    {
        "name": "The Midway",
        "base_url": "https://themidwaysf.com",
        "calendar_path": "/events/",
        "scraper_class": MidwayScraper,
    },
    {
        "name": "The Independent",
        "base_url": "https://www.theindependentsf.com",
        "calendar_path": "/calendar/",
        "scraper_class": IndependentScraper,
    },
    {
        "name": "Bottom of the Hill",
        "base_url": "https://www.bottomofthehill.com",
        "calendar_path": "/calendar.html",
        "scraper_class": BottomOfTheHillScraper,
    },
    {
        "name": "Audio Nightclub",
        "base_url": "https://m.audiosf.com",
        "calendar_path": "/events/",
        "scraper_class": AudioNightclubScraper,
    },
    {
        "name": "Reverb",
        "base_url": "https://reverb-sf.com",
        "calendar_path": "/",
        "scraper_class": ReverbScraper,
    },
    {
        "name": "Public Works",
        "base_url": "https://publicsf.com",
        "calendar_path": "/calendar/",
        "scraper_class": PublicWorksScraper,
    },
    {
        "name": "Rickshaw Stop",
        "base_url": "https://rickshawstop.com",
        "calendar_path": "/calendar/",
        "scraper_class": RickshawStopScraper,
    },
    {
        "name": "Bimbo's 365 Club",
        "base_url": "https://bimbos365club.com",
        "calendar_path": "/shows/",
        "scraper_class": Bimbos365Scraper,
    },
    {
        "name": "Gray Area",
        "base_url": "https://grayarea.org",
        "calendar_path": "/visit/events/",
        "scraper_class": GrayAreaScraper,
    },
    {
        "name": "The Chapel",
        "base_url": "https://thechapelsf.com",
        "calendar_path": "/calendar/",
        "scraper_class": ChapelScraper,
    },
]


def _get_venue_starred_status(venue_name):
    """Get the starred status for a venue from database"""
    from storage import Database

    db = Database()
    return db.is_venue_starred(venue_name)


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
    from storage import Database

    venue = get_venue_by_name(venue_name)
    if not venue:
        return False, f"Venue '{venue_name}' not found"

    db = Database()
    if db.is_venue_starred(venue["name"]):
        return True, f"'{venue['name']}' is already starred"

    success = db.star_venue(venue["name"])
    if success:
        return True, f"Starred '{venue['name']}'"
    else:
        return False, f"Failed to star '{venue['name']}'"


def unstar_venue(venue_name: str):
    """Unstar a venue"""
    from storage import Database

    venue = get_venue_by_name(venue_name)
    if not venue:
        return False, f"Venue '{venue_name}' not found"

    db = Database()
    if not db.is_venue_starred(venue["name"]):
        return True, f"'{venue['name']}' was not starred"

    success = db.unstar_venue(venue["name"])
    if success:
        return True, f"Unstarred '{venue['name']}'"
    else:
        return False, f"Failed to unstar '{venue['name']}'"


def get_starred_venues():
    """Get list of starred venue names"""
    from storage import Database

    db = Database()
    return db.get_starred_venues()


def get_venue_names():
    """Get list of all venue names"""
    return [venue["name"] for venue in VENUES_CONFIG]


def get_venues_config():
    """Get venues in new format"""
    return VENUES_CONFIG
