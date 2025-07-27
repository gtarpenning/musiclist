#!/usr/bin/env python3
"""
Parallel scraping module for musiclist project.

Handles concurrent venue scraping with progress tracking using Rich library.
"""

import concurrent.futures
from datetime import date
from typing import List, Dict, Tuple, Callable, Any
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
)
from rich.console import Console

from models import Event, Venue
from storage import Cache, Database


class ParallelScraper:
    """Handles parallel scraping of multiple venues with progress tracking"""

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.console = Console()
        self.cache = Cache()
        self.db = Database()

    def _scrape_single_venue(
        self, venue_config: Dict[str, Any], force_refresh: bool = False
    ) -> Tuple[str, List[Event], bool]:
        """
        Scrape a single venue and return results.

        Returns:
            Tuple of (venue_name, events, used_cache)
        """
        venue_fields = {
            "name": venue_config["name"],
            "base_url": venue_config["base_url"],
            "calendar_path": venue_config["calendar_path"],
        }
        venue = Venue(**venue_fields)
        venue_name = venue.name

        # Save venue to database
        self.db.save_venue(venue)

        # Check if we have fresh cached data and don't need to scrape
        if not force_refresh and self.db.is_venue_data_fresh(
            venue_name, cache_hours=24
        ):
            # Use cached data - no need to scrape
            all_cached_events = self.db.get_cached_events_for_venue(venue_name)
            # Filter out past events
            today = date.today()
            future_events = [
                event for event in all_cached_events if event.date >= today
            ]
            return venue_name, future_events, True

        # Data is stale or force refresh requested - scrape fresh data
        scraper_class = venue_config["scraper_class"]
        scraper = scraper_class(venue, self.cache)

        try:
            # Scrape events
            events = scraper.get_events()
            if events:
                # Save all events to database (preserves existing pins)
                self.db.save_events(events)

                # Filter out past events
                today = date.today()
                future_events = [event for event in events if event.date >= today]
                return venue_name, future_events, False
            else:
                # No events found from scraping, try cached data as fallback
                all_cached_events = self.db.get_cached_events_for_venue(venue_name)
                future_events = [
                    event for event in all_cached_events if event.date >= today
                ]
                return venue_name, future_events, True

        except Exception as e:
            # Error occurred, try cached data as fallback
            all_cached_events = self.db.get_cached_events_for_venue(venue_name)
            today = date.today()
            future_events = [
                event for event in all_cached_events if event.date >= today
            ]
            return venue_name, future_events, True

    def scrape_venues_parallel(
        self, venues_config: List[Dict[str, Any]], force_refresh: bool = False
    ) -> Tuple[List[Event], Dict[str, int]]:
        """
        Scrape multiple venues in parallel with progress tracking.

        Returns:
            Tuple of (all_events, venue_stats)
        """
        all_events = []
        venue_stats = {}

        # Create progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=self.console,
            transient=False,
        ) as progress:

            # Add main progress task
            main_task = progress.add_task(
                "Scraping venues...", total=len(venues_config)
            )

            # Use ThreadPoolExecutor for I/O bound tasks
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.max_workers
            ) as executor:
                # Submit all scraping tasks
                future_to_venue = {
                    executor.submit(
                        self._scrape_single_venue, venue_config, force_refresh
                    ): venue_config["name"]
                    for venue_config in venues_config
                }

                # Process completed tasks as they finish
                for future in concurrent.futures.as_completed(future_to_venue):
                    venue_name = future_to_venue[future]

                    try:
                        venue_name_result, events, used_cache = future.result()
                        all_events.extend(events)
                        venue_stats[venue_name_result] = len(events)

                        # Update progress with venue completion
                        cache_status = " (cached)" if used_cache else ""
                        progress.update(
                            main_task,
                            advance=1,
                            description=f"Updated: {venue_name_result}{cache_status}",
                        )

                    except Exception as e:
                        # Handle individual venue failures gracefully
                        venue_stats[venue_name] = 0
                        progress.update(
                            main_task, advance=1, description=f"Failed: {venue_name}"
                        )
                        self.console.print(
                            f"[red]Error scraping {venue_name}: {e}[/red]"
                        )

            # Final status
            progress.update(
                main_task, description=f"Completed scraping {len(venues_config)} venues"
            )

        return all_events, venue_stats

    def scrape_venues_for_calendar(
        self, venues_config: List[Dict[str, Any]], force_refresh: bool = False
    ) -> Tuple[List[Event], Dict[str, int]]:
        """
        Scrape venues for calendar display with date filtering.

        This method includes additional filtering logic for calendar mode.
        """
        all_events, venue_stats = self.scrape_venues_parallel(
            venues_config, force_refresh
        )

        # Filter events for current and next month (calendar mode)
        from dateutil.relativedelta import relativedelta

        today = date.today()
        start_date = today.replace(day=1)  # First day of current month
        end_date = (start_date + relativedelta(months=2)).replace(
            day=1
        ) - relativedelta(
            days=1
        )  # Last day of next month

        filtered_events = [
            event for event in all_events if start_date <= event.date <= end_date
        ]

        return filtered_events, venue_stats
