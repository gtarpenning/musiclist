from datetime import date
from typing import List, Dict
import re

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.columns import Columns

from models import Event
from storage import Database
from .colors import (
    DATE_COLOR,
    TIME_COLOR,
    ARTISTS_COLOR,
    VENUE_COLOR,
    COST_COLOR,
    SUCCESS_COLOR,
    ERROR_COLOR,
    INFO_COLOR,
    WARNING_COLOR,
    HEADER_COLOR,
    WEEKEND_COLOR,
    PINNED_COLOR,
    PIN_MARKER_COLOR,
    style,
    link_style,
    ColorKey,
)


class Terminal:
    def __init__(self):
        self.console = Console()

    def format_cost(self, cost_str: str) -> str:
        """Clean and format cost string by removing extra text and formatting ranges"""
        if not cost_str or cost_str.lower() in ["tbd", "none"]:
            return ""

        if cost_str.lower() == "free":
            return "Free"

        # Extract all dollar amounts from the string
        price_pattern = r"\$?(\d+(?:\.\d{2})?)"
        prices = re.findall(price_pattern, cost_str)

        if not prices:
            return ""

        # Convert to floats and remove duplicates
        unique_prices = []
        for price in prices:
            price_float = float(price)
            if price_float not in unique_prices:
                unique_prices.append(price_float)

        unique_prices.sort()

        if len(unique_prices) == 1:
            # Single price
            price = (
                int(unique_prices[0])
                if unique_prices[0] == int(unique_prices[0])
                else unique_prices[0]
            )
            return f"${price}"
        elif len(unique_prices) == 2:
            # Price range
            min_price = (
                int(unique_prices[0])
                if unique_prices[0] == int(unique_prices[0])
                else unique_prices[0]
            )
            max_price = (
                int(unique_prices[1])
                if unique_prices[1] == int(unique_prices[1])
                else unique_prices[1]
            )
            return f"${min_price}-{max_price}"
        else:
            # Multiple prices, show range
            min_price = (
                int(unique_prices[0])
                if unique_prices[0] == int(unique_prices[0])
                else unique_prices[0]
            )
            max_price = (
                int(unique_prices[-1])
                if unique_prices[-1] == int(unique_prices[-1])
                else unique_prices[-1]
            )
            return f"${min_price}-{max_price}"

    def display_events(self, events: List[Event], title: str = "Upcoming Events"):
        """Display events in a formatted table"""
        if not events:
            self.console.print(style(f"No events found for {title}", "warning"))
            return

        table = Table(
            title=title, show_header=True, header_style=f"bold {HEADER_COLOR}"
        )

        table.add_column("Date", style=DATE_COLOR, width=12)
        table.add_column("Time", style=TIME_COLOR, width=8)
        table.add_column("Artists", style=ARTISTS_COLOR, width=35)
        table.add_column("Venue", style=VENUE_COLOR, width=20)
        table.add_column("Cost", style=COST_COLOR, width=12)

        for event in events:
            date_str = event.date.strftime("%b %d")
            time_str = event.time.strftime("%I:%M %p") if event.time else ""
            artists_str = event.artists_display
            venue_str = event.venue
            cost_str = self.format_cost(event.cost or "TBD")

            # Truncate long artist names
            if len(artists_str) > 33:
                artists_str = artists_str[:30] + "..."

            table.add_row(date_str, time_str, artists_str, venue_str, cost_str)

        self.console.print(table)
        self.console.print(f"\n{style(f'Found {len(events)} events', 'dim')}")

    def display_calendar_events(
        self, events: List[Event], title: str = "🎵 Upcoming Music Events"
    ):
        """Display events in a calendar view with clickable links, day of week, weekend highlighting, venue stars, pin status, and day separators"""
        if not events:
            self.console.print(style("No events found", "warning"))
            return

        table = Table(
            title=title, show_header=True, header_style=f"bold {HEADER_COLOR}"
        )

        table.add_column("Pin", style=PIN_MARKER_COLOR, width=4)
        table.add_column("Date", style=DATE_COLOR, width=16)
        table.add_column("Time", style=TIME_COLOR, width=8)
        table.add_column("Event", style=ARTISTS_COLOR, width=37)
        table.add_column("Venue", style=VENUE_COLOR, width=27)
        table.add_column("Cost", style=COST_COLOR, width=15)

        # Get starred venues for icon display
        db = Database()
        starred_venues = db.get_starred_venues()

        current_date = None
        event_counter = 0

        for i, event in enumerate(events):
            # Check if we need to add a day separator
            if current_date and current_date != event.date:
                # Add blank row between different days
                table.add_row("", "", "", "", "", "")

            current_date = event.date
            event_counter += 1

            # Pin status
            pin_status = "📌" if event.pinned else f"{event_counter:2d}"

            # Format date with day of week
            day_of_week = event.date.strftime("%a").upper()  # MON, TUE, etc.
            date_str = f"{day_of_week} {event.date.strftime('%b %d')}"

            # Check if it's a weekend (Friday or Saturday)
            is_weekend = event.date.weekday() in [4, 5]  # 4=Friday, 5=Saturday

            # Apply weekend highlighting to the date
            if is_weekend:
                date_str = style(date_str, "weekend")

            time_str = event.time.strftime("%I:%M %p") if event.time else "TBD"
            cost_str = self.format_cost(event.cost or "TBD")

            # Add star icon for starred venues
            venue_str = event.venue
            if event.venue in starred_venues:
                venue_str = f"⭐ {event.venue}"

            # Create clickable event link
            artists_str = event.artists_display

            # Format case based on pin status: lowercase for regular, uppercase for pinned
            if event.pinned:
                artists_str = artists_str.upper()
            else:
                artists_str = artists_str.lower()

            if len(artists_str) > 34:
                artists_str = artists_str[:31] + "..."

            # Apply special styling for pinned events
            if event.pinned:
                pin_status = style("📌", "pin_marker", bold=True)
                if event.url:
                    event_link = link_style(artists_str, event.url, "pinned")
                else:
                    event_link = style(artists_str, "pinned")
                venue_str = style(venue_str, "pinned")
                cost_str = style(cost_str, "pinned")
            # Apply weekend highlighting to the entire event if weekend
            elif is_weekend:
                if event.url:
                    # For weekends, make link with weekend color instead of nesting markup
                    event_link = link_style(artists_str, event.url, "weekend")
                else:
                    event_link = style(artists_str, "weekend")
                venue_str = style(venue_str, "weekend")
                cost_str = style(cost_str, "weekend")
            else:
                # Make the event title clickable if there's a URL
                if event.url:
                    event_link = f"[link={event.url}]{artists_str}[/link]"
                else:
                    event_link = artists_str

            table.add_row(
                pin_status, date_str, time_str, event_link, venue_str, cost_str
            )

        self.console.print(table)

        # Count weekend events and pinned events for summary
        weekend_events = sum(1 for event in events if event.date.weekday() in [4, 5])
        starred_events = sum(1 for event in events if event.venue in starred_venues)
        pinned_events = sum(1 for event in events if event.pinned)

        summary_parts = [f"📅 Found {len(events)} upcoming events"]
        if pinned_events > 0:
            summary_parts.append(f"📌 {pinned_events} pinned")
        if weekend_events > 0:
            summary_parts.append(f"🎉 {weekend_events} weekend shows")
        if starred_events > 0:
            summary_parts.append(f"⭐ {starred_events} at starred venues")
        summary_parts.append("Click on event names to view details")

        self.console.print(f"\n{style(' • '.join(summary_parts), 'dim')}")

        # Add pin interaction help
        if events:
            pin_help = "💡 Use event numbers to pin/unpin: music pin <number> or music unpin <number>"
            artist_help = '💡 Pin by artist name: music pin "Artist Name" or show pinned: music pinned'
            self.console.print(f"\n{style(pin_help, 'dim')}")
            self.console.print(style(artist_help, "dim"))

    def display_venue_summary(self, venue_stats: Dict[str, int]):
        """Display a summary of venues and their event counts with starring info"""
        if not venue_stats:
            return

        # Create venue summary table
        venue_table = Table(
            title="📍 Venue Summary",
            show_header=True,
            header_style=f"bold {VENUE_COLOR}",
        )
        venue_table.add_column("Venue", style=ARTISTS_COLOR, width=35)
        venue_table.add_column(
            "Events Found", style=DATE_COLOR, justify="right", width=15
        )
        venue_table.add_column("Status", style=SUCCESS_COLOR, width=15)

        # Get starred venues for display
        db = Database()
        starred_venues = db.get_starred_venues()

        total_events = 0
        for venue_name, count in venue_stats.items():
            total_events += count
            status = "✓ Active" if count > 0 else "⚠️ No Events"
            status_color = "success" if count > 0 else "warning"

            # Add star icon for starred venues
            display_name = venue_name
            if venue_name in starred_venues:
                display_name = f"⭐ {venue_name}"

            venue_table.add_row(display_name, str(count), style(status, status_color))

        # Add total row
        venue_table.add_section()
        venue_table.add_row(
            style("Total", "bold"),
            style(str(total_events), "bold"),
            style("All Venues", "success", bold=True),
        )

        self.console.print(venue_table)

        # Add helpful info with starring tips
        tips = [
            "Events are cached for faster subsequent loads",
            "Click event names to buy tickets",
        ]
        if starred_venues:
            tips.append(f"⭐ {len(starred_venues)} starred venues highlighted")
        else:
            tips.append('Use --star-venue "VENUE NAME" to star favorites')

        tips_str = " • ".join(tips)
        self.console.print(f"\n{style(f'💡 Tip: {tips_str}', 'dim')}")

    def show_scraping_progress(self, venue_name: str):
        """Show progress spinner for scraping"""
        return Progress(
            SpinnerColumn(),
            TextColumn(f"[bold {INFO_COLOR}]Scraping {venue_name}..."),
            console=self.console,
            transient=True,
        )

    def show_success(self, message: str):
        """Show success message"""
        self.console.print(f"{style('✓', 'success')} {message}")

    def show_error(self, message: str):
        """Show error message"""
        self.console.print(f"{style('✗', 'error')} {message}")

    def show_info(self, message: str):
        """Show info message"""
        self.console.print(f"{style('ℹ', 'info')} {message}")

    def show_header(self, title: str):
        """Show application header"""
        header = Panel(
            Text(title, style=f"bold {ARTISTS_COLOR}", justify="center"),
            style=HEADER_COLOR,
            padding=(1, 2),
        )
        self.console.print(header)
