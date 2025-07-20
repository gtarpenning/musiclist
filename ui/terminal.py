from datetime import date
from typing import List

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.text import Text

from models import Event


class Terminal:
    def __init__(self):
        self.console = Console()

    def display_events(self, events: List[Event], title: str = "Upcoming Events"):
        """Display events in a formatted table"""
        if not events:
            self.console.print(f"[yellow]No events found for {title}[/yellow]")
            return

        table = Table(title=title, show_header=True, header_style="bold blue")

        table.add_column("Date", style="cyan", width=12)
        table.add_column("Time", style="green", width=8)
        table.add_column("Artists", style="bright_white", width=35)
        table.add_column("Venue", style="magenta", width=20)
        table.add_column("Cost", style="yellow", width=12)

        for event in events:
            date_str = event.date.strftime("%b %d")
            time_str = event.time.strftime("%I:%M %p") if event.time else ""
            artists_str = event.artists_display
            venue_str = event.venue
            cost_str = event.cost or "TBD"

            # Truncate long artist names
            if len(artists_str) > 33:
                artists_str = artists_str[:30] + "..."

            table.add_row(date_str, time_str, artists_str, venue_str, cost_str)

        self.console.print(table)
        self.console.print(f"\n[dim]Found {len(events)} events[/dim]")

    def show_scraping_progress(self, venue_name: str):
        """Show progress spinner for scraping"""
        return Progress(
            SpinnerColumn(),
            TextColumn(f"[bold blue]Scraping {venue_name}..."),
            console=self.console,
            transient=True,
        )

    def show_success(self, message: str):
        """Show success message"""
        self.console.print(f"[green]✓[/green] {message}")

    def show_error(self, message: str):
        """Show error message"""
        self.console.print(f"[red]✗[/red] {message}")

    def show_info(self, message: str):
        """Show info message"""
        self.console.print(f"[blue]ℹ[/blue] {message}")

    def show_header(self, title: str):
        """Show application header"""
        header = Panel(
            Text(title, style="bold bright_white", justify="center"),
            style="blue",
            padding=(1, 2),
        )
        self.console.print(header)
