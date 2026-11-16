#!/usr/bin/env python3
"""
Centralized venue configuration for the musiclist project.

This configuration is used by:
- cli.py for scraping and calendar display
- `music doctor` for live scraper health checks
- tests/ for fixture-driven parser tests

Adding a venue usually means picking the platform scraper that matches its
site (TicketWeb, SeeTickets, JSON-LD, DICE, Rockhouse) and adding a line
here, with its kind and city (see VENUE_KINDS); write a dedicated scraper
only for one-off sites.
"""

import unicodedata

from scrapers import (
    AnotherPlanetScraper,
    AudioNightclubScraper,
    BottomOfTheHillScraper,
    CafeDuNordScraper,
    DiceScraper,
    DnaLoungeScraper,
    Folsom1015Scraper,
    GrayAreaScraper,
    JsonLdScraper,
    NineteenHzScraper,
    PublicWorksScraper,
    RegencyBallroomScraper,
    RockhouseScraper,
    SeeTicketsScraper,
    SwedishAmericanHallScraper,
    TicketWebScraper,
    WarfieldScraper,
)

# Number of venues to scrape in parallel
DEFAULT_MAX_WORKERS = 8

# Every venue has a "kind" (the website's type filter, in this order):
#   bar    a bar with a stage          club   a dance club
#   small  rooms up to ~500 people     mid    ~500-1,500 (August Hall, the Fillmore)
#   large  ~1,500 and up               arena  arenas and stadiums
#   other  arts and community spaces
# and a "city" when it isn't San Francisco (the website's city selector).
VENUE_KINDS = ["bar", "club", "small", "mid", "large", "arena", "other"]
CITIES = ["San Francisco", "Oakland", "Berkeley"]
DEFAULT_CITY = "San Francisco"


VENUES_CONFIG = [
    # --- TicketWeb plugin --------------------------------------------------
    {
        "name": "The Independent",
        "area": "NoPa",
        "kind": "small",
        "base_url": "https://www.theindependentsf.com",
        # /calendar/ is an AJAX widget; the homepage carries the full list
        "calendar_path": "/",
        "scraper_class": TicketWebScraper,
    },
    {
        "name": "August Hall",
        "area": "Union Square",
        "kind": "mid",
        "base_url": "https://www.augusthallsf.com",
        "calendar_path": "/events/",
        "scraper_class": TicketWebScraper,
    },
    {
        "name": "Brick & Mortar Music Hall",
        "area": "Mission",
        "kind": "small",
        "base_url": "https://www.brickandmortarmusic.com",
        "calendar_path": "/calendar/",
        "scraper_class": TicketWebScraper,
    },
    {
        "name": "Neck of the Woods",
        "area": "Inner Richmond",
        "kind": "small",
        "base_url": "https://www.neckofthewoodssf.com",
        "calendar_path": "/calendar/",
        "scraper_class": TicketWebScraper,
    },
    {
        "name": "Bimbo's 365 Club",
        "area": "North Beach",
        "kind": "mid",
        "base_url": "https://bimbos365club.com",
        "calendar_path": "/shows/",
        "scraper_class": TicketWebScraper,
    },
    # --- SeeTickets plugin -------------------------------------------------
    {
        "name": "The Chapel",
        "area": "Mission",
        "kind": "small",
        "base_url": "https://thechapelsf.com",
        "calendar_path": "/calendar/",
        "scraper_class": SeeTicketsScraper,
    },
    {
        "name": "Rickshaw Stop",
        "area": "Hayes Valley",
        "kind": "small",
        "base_url": "https://rickshawstop.com",
        "calendar_path": "/calendar/",
        "scraper_class": SeeTicketsScraper,
    },
    {
        "name": "Hotel Utah Saloon",
        "area": "SoMa",
        "kind": "bar",
        "base_url": "https://hotelutah.com",
        "calendar_path": "/calendar/",
        "scraper_class": SeeTicketsScraper,
    },
    # --- schema.org JSON-LD ------------------------------------------------
    {
        "name": "The Fillmore",
        "area": "Fillmore",
        "kind": "mid",
        "base_url": "https://www.thefillmore.com",
        "calendar_path": "/shows",
        "scraper_class": JsonLdScraper,
    },
    {
        "name": "The Masonic",
        "area": "Nob Hill",
        "kind": "large",
        "base_url": "https://www.sfmasonic.com",
        "calendar_path": "/shows",
        "scraper_class": JsonLdScraper,
    },
    {
        "name": "The Midway",
        "area": "Dogpatch",
        "kind": "club",
        "base_url": "https://themidwaysf.com",
        "calendar_path": "/events/",
        "scraper_class": JsonLdScraper,
    },
    # --- DICE widget -------------------------------------------------------
    {
        "name": "Kilowatt",
        "area": "Mission",
        "kind": "bar",
        "base_url": "https://kilowattbar.com",
        "calendar_path": "/events",
        "scraper_class": DiceScraper,
    },
    {
        "name": "The Knockout",
        "area": "Mission",
        "kind": "bar",
        "base_url": "https://theknockoutsf.com",
        "calendar_path": "/",
        "scraper_class": DiceScraper,
    },
    {
        "name": "Halcyon",
        "area": "SoMa",
        "kind": "club",
        "base_url": "https://halcyon-sf.com",
        "calendar_path": "/main/",
        "scraper_class": DiceScraper,
    },
    # --- one-off sites -----------------------------------------------------
    {
        "name": "Café du Nord",
        "area": "Upper Market",
        "kind": "small",
        "base_url": "https://cafedunord.com",
        "calendar_path": "/shows",
        "scraper_class": CafeDuNordScraper,
    },
    {
        "name": "Swedish American Hall",
        "area": "Upper Market",
        "kind": "small",
        "base_url": "https://cafedunord.com",
        "calendar_path": "/shows",
        "scraper_class": SwedishAmericanHallScraper,
    },
    {
        "name": "Bill Graham Civic Auditorium",
        "area": "Civic Center",
        "kind": "large",
        "base_url": "https://billgrahamcivic.com",
        "calendar_path": "/event-listing/",
        "scraper_class": AnotherPlanetScraper,
    },
    {
        "name": "The Warfield",
        "area": "Mid-Market",
        "kind": "large",
        "base_url": "https://www.thewarfieldtheatre.com",
        "calendar_path": "/events/",
        "scraper_class": WarfieldScraper,
    },
    {
        "name": "The Regency Ballroom",
        "area": "Polk Gulch",
        "kind": "mid",
        "base_url": "https://www.theregencyballroom.com",
        "calendar_path": "/shows/",
        "scraper_class": RegencyBallroomScraper,
    },
    {
        "name": "Great American Music Hall",
        "area": "Tenderloin",
        "kind": "mid",
        "base_url": "https://gamh.com",
        "calendar_path": "/calendar/",
        "scraper_class": SeeTicketsScraper,
    },
    {
        "name": "Bottom of the Hill",
        "area": "Potrero Hill",
        "kind": "small",
        "base_url": "https://www.bottomofthehill.com",
        "calendar_path": "/calendar.html",
        "scraper_class": BottomOfTheHillScraper,
    },
    {
        "name": "Public Works",
        "area": "Mission",
        "kind": "club",
        "base_url": "https://publicsf.com",
        "calendar_path": "/calendar/",
        "scraper_class": PublicWorksScraper,
    },
    {
        "name": "1015 Folsom",
        "area": "SoMa",
        "kind": "club",
        "base_url": "https://1015.com",
        "calendar_path": "/calendar/",
        "scraper_class": Folsom1015Scraper,
    },
    {
        "name": "DNA Lounge",
        "area": "SoMa",
        "kind": "club",
        "base_url": "https://www.dnalounge.com",
        "calendar_path": "/calendar/latest.html",
        "scraper_class": DnaLoungeScraper,
    },
    {
        "name": "Audio Nightclub",
        "area": "SoMa",
        "kind": "club",
        "base_url": "https://m.audiosf.com",
        "calendar_path": "/events/",
        "scraper_class": AudioNightclubScraper,
    },
    {
        "name": "Boom Boom Room",
        "area": "Fillmore",
        "kind": "club",
        "base_url": "https://boomboomroom.com",
        "calendar_path": "/",
        "scraper_class": RockhouseScraper,
    },
    {
        "name": "Gray Area",
        "area": "Mission",
        "kind": "other",
        "base_url": "https://grayarea.org",
        "calendar_path": "/visit/events/",
        "scraper_class": GrayAreaScraper,
    },
    # Clubs without a scrapable calendar of their own, read from 19hz.info.
    # home_url is what the website links to (the calendar URL is 19hz's page).
    {
        "name": "The Great Northern",
        "area": "SoMa",
        "kind": "club",
        "base_url": "https://19hz.info",
        "calendar_path": "/eventlisting_BayArea.php",
        "home_url": "https://www.thegreatnorthernsf.com/",
        "scraper_class": NineteenHzScraper,
    },
    {
        "name": "Monarch",
        "area": "SoMa",
        "kind": "club",
        "base_url": "https://19hz.info",
        "calendar_path": "/eventlisting_BayArea.php",
        "home_url": "https://www.monarchsf.com/",
        "scraper_class": NineteenHzScraper,
    },
    # --- East Bay ------------------------------------------------------------
    {
        "name": "Fox Theater",
        "area": "Uptown",
        "kind": "large",
        "city": "Oakland",
        "base_url": "https://thefoxoakland.com",
        # /calendar/ is a JS grid; the homepage carries the full list
        "calendar_path": "/",
        "scraper_class": AnotherPlanetScraper,
    },
    {
        "name": "Thee Stork Club",
        "area": "Uptown",
        "kind": "bar",
        "city": "Oakland",
        "base_url": "https://theestorkclub.com",
        "calendar_path": "/calendar/",
        "scraper_class": SeeTicketsScraper,
    },
    {
        "name": "Greek Theatre",
        "area": "UC Berkeley",
        "kind": "large",
        "city": "Berkeley",
        "base_url": "https://thegreekberkeley.com",
        "calendar_path": "/event-listing/",
        "scraper_class": AnotherPlanetScraper,
    },
]


def fold(text: str) -> str:
    """Lowercase and strip accents so 'cafe' matches 'Café du Nord'."""
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()


def _starred_names():
    from storage import Database

    return set(Database().get_starred_venues())


def get_enabled_venues():
    """Get list of enabled venue configurations with starred status"""
    starred = _starred_names()
    venues = []
    for venue in VENUES_CONFIG:
        if venue.get("enabled", True):
            venue_copy = venue.copy()
            venue_copy["starred"] = venue["name"] in starred
            venues.append(venue_copy)
    return venues


def get_venue_by_name(name: str):
    """Get venue configuration by exact (accent/case-insensitive) name with starred status"""
    target = fold(name)
    for venue in VENUES_CONFIG:
        if fold(venue["name"]) == target:
            venue_copy = venue.copy()
            venue_copy["starred"] = venue["name"] in _starred_names()
            return venue_copy
    return None


def _ensure_venue_row(venue_config):
    """Starring needs a venues row even before the venue was ever scraped."""
    from models import Venue
    from storage import Database

    Database().save_venue(
        Venue(
            venue_config["name"],
            venue_config["base_url"],
            venue_config.get("calendar_path", "/"),
        )
    )


def star_venue(venue_name: str):
    """Star a venue"""
    from storage import Database

    venue = get_venue_by_name(venue_name)
    if not venue:
        return False, f"Venue '{venue_name}' not found"

    db = Database()
    if db.is_venue_starred(venue["name"]):
        return True, f"'{venue['name']}' is already starred"

    _ensure_venue_row(venue)
    if db.star_venue(venue["name"]):
        return True, f"Starred '{venue['name']}'"
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

    if db.unstar_venue(venue["name"]):
        return True, f"Unstarred '{venue['name']}'"
    return False, f"Failed to unstar '{venue['name']}'"


def get_starred_venues():
    """Get list of starred venue names"""
    from storage import Database

    return Database().get_starred_venues()


def get_venue_names():
    """Get list of all venue names"""
    return [venue["name"] for venue in VENUES_CONFIG]


def get_venues_config():
    """Get all venue configurations"""
    return VENUES_CONFIG
