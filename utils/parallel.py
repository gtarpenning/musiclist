#!/usr/bin/env python3
"""
Venue refresh orchestration.

Every view (calendar, venue, starred, scrape, doctor) refreshes venues
through refresh_venues() and then reads events back from the database, so
displayed events always carry their database ids and pin state.
"""

import concurrent.futures
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
)

from models import Event, Venue
from storage import Cache, Database

FRESH_HOURS = 24


@dataclass
class VenueResult:
    name: str
    status: str  # "fresh" | "cached" | "empty" | "error"
    count: int = 0
    error: Optional[str] = None
    elapsed: float = 0.0
    events: List[Event] = field(default_factory=list, repr=False)

    @property
    def ok(self) -> bool:
        return self.status in ("fresh", "cached")


def venue_from_config(venue_config: Dict[str, Any]) -> Venue:
    return Venue(
        name=venue_config["name"],
        base_url=venue_config["base_url"],
        calendar_path=venue_config.get("calendar_path", "/"),
    )


def refresh_venue(
    venue_config: Dict[str, Any],
    db: Database,
    cache: Cache,
    force_refresh: bool = False,
    save: bool = True,
) -> VenueResult:
    """Scrape one venue unless its data is fresh; store results in the database."""
    venue = venue_from_config(venue_config)
    db.save_venue(venue)
    started = time.time()

    if not force_refresh and db.is_venue_data_fresh(
        venue.name, cache_hours=FRESH_HOURS
    ):
        count = len(db.get_cached_events_for_venue(venue.name))
        return VenueResult(venue.name, "cached", count)

    scraper = venue_config["scraper_class"](venue, cache, force_refresh=force_refresh)
    try:
        events = scraper.scrape()
    except Exception as e:
        return VenueResult(
            venue.name, "error", error=str(e)[:200], elapsed=time.time() - started
        )

    today = date.today()
    upcoming = [e for e in events if e.date >= today]
    elapsed = time.time() - started
    if not upcoming:
        # Reachable but nothing parsed: keep existing rows (a layout change
        # shouldn't wipe the calendar) and report it so drift gets noticed.
        return VenueResult(venue.name, "empty", elapsed=elapsed)

    if save:
        db.save_events(upcoming, prune_missing=True)
    return VenueResult(
        venue.name, "fresh", len(upcoming), elapsed=elapsed, events=upcoming
    )


def refresh_venues(
    venues_config: List[Dict[str, Any]],
    force_refresh: bool = False,
    max_workers: int = 6,
    db: Optional[Database] = None,
    cache: Optional[Cache] = None,
    console: Optional[Console] = None,
    show_progress: bool = True,
    save: bool = True,
) -> Dict[str, VenueResult]:
    """Refresh venues in parallel with a progress bar; returns results keyed by venue name."""
    db = db or Database()
    cache = cache or Cache()
    console = console or Console()
    results: Dict[str, VenueResult] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
        transient=True,
        disable=not show_progress,
    ) as progress:
        task = progress.add_task("Checking venues...", total=len(venues_config))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    refresh_venue, cfg, db, cache, force_refresh, save
                ): cfg["name"]
                for cfg in venues_config
            }
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                except (
                    Exception
                ) as e:  # defensive: refresh_venue already catches scrape errors
                    result = VenueResult(name, "error", error=str(e)[:200])
                results[name] = result
                progress.update(task, advance=1, description=f"{result.status}: {name}")

    # Preserve config order for stable summaries
    return {
        cfg["name"]: results[cfg["name"]]
        for cfg in venues_config
        if cfg["name"] in results
    }


class ParallelScraper:
    """Backwards-compatible wrapper around refresh_venues()."""

    def __init__(self, max_workers: int = 6):
        self.max_workers = max_workers
        self.console = Console()
        self.cache = Cache()
        self.db = Database()

    def scrape_venues_parallel(self, venues_config, force_refresh: bool = False):
        results = refresh_venues(
            venues_config,
            force_refresh,
            self.max_workers,
            self.db,
            self.cache,
            self.console,
        )
        names = [cfg["name"] for cfg in venues_config]
        events = self.db.get_events(venues=names)
        return events, {name: r.count for name, r in results.items()}
