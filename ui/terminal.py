from datetime import date
from typing import List, Dict

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.columns import Columns

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

    def display_calendar_events(self, events: List[Event], title: str = "🎵 Upcoming Music Events"):
        """Display events in a calendar view with clickable links"""
        if not events:
            self.console.print("[yellow]No events found[/yellow]")
            return

        table = Table(title=title, show_header=True, header_style="bold blue")

        table.add_column("Date", style="cyan", width=12)
        table.add_column("Time", style="green", width=8) 
        table.add_column("Event", style="bright_white", width=45)
        table.add_column("Venue", style="magenta", width=25)
        table.add_column("Cost", style="yellow", width=15)

        for event in events:
            date_str = event.date.strftime("%b %d")
            time_str = event.time.strftime("%I:%M %p") if event.time else "TBD"
            venue_str = event.venue
            cost_str = event.cost or "TBD"
            
            # Create clickable event link
            artists_str = event.artists_display
            if len(artists_str) > 42:
                artists_str = artists_str[:39] + "..."
            
            # Make the event title clickable if there's a URL
            if event.url:
                event_link = f"[link={event.url}]{artists_str}[/link]"
            else:
                event_link = artists_str

            table.add_row(date_str, time_str, event_link, venue_str, cost_str)

        self.console.print(table)
        self.console.print(f"\n[dim]📅 Found {len(events)} upcoming events • Click on event names to view details[/dim]")

    def display_venue_summary(self, venue_stats: Dict[str, int]):
        """Display a summary of venues and their event counts"""
        if not venue_stats:
            return
            
        self.console.print("\n")
        
        # Create venue summary table
        venue_table = Table(title="📍 Venue Summary", show_header=True, header_style="bold magenta")
        venue_table.add_column("Venue", style="bright_white", width=30)
        venue_table.add_column("Events Found", style="cyan", justify="right", width=15)
        venue_table.add_column("Status", style="green", width=15)
        
        total_events = 0
        for venue_name, count in venue_stats.items():
            total_events += count
            status = "✓ Active" if count > 0 else "⚠️ No Events"
            status_style = "green" if count > 0 else "yellow"
            
            venue_table.add_row(
                venue_name, 
                str(count),
                f"[{status_style}]{status}[/{status_style}]"
            )
        
        # Add total row
        venue_table.add_section()
        venue_table.add_row(
            "[bold]Total[/bold]", 
            f"[bold]{total_events}[/bold]",
            "[bold green]All Venues[/bold green]"
        )
        
        self.console.print(venue_table)
        
        # Add helpful info
        self.console.print(f"\n[dim]💡 Tip: Events are cached for faster subsequent loads • Click event names to buy tickets[/dim]")

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
