#!/usr/bin/env python3
"""
Test runner for musiclist project
Usage: python tests/run_tests.py [venue_name] [--generate]
"""

import sys
import unittest
import os
from rich.console import Console
from rich.table import Table

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from venues_config import get_enabled_venues, get_enabled_venue_names

console = Console()


def discover_and_run_tests(test_pattern="test_*.py"):
    """Discover and run tests with rich output"""

    # Discover tests - include both old individual test files and new dynamic tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(__file__)

    suite = unittest.TestSuite()

    # Load dynamic venue tests
    try:
        from tests.dynamic_venue_tests import generated_classes

        console.print(
            f"[blue]Loading {len(generated_classes)} dynamically generated venue test classes[/blue]"
        )

        for test_class in generated_classes:
            class_suite = loader.loadTestsFromTestCase(test_class)
            suite.addTest(class_suite)

    except ImportError as e:
        console.print(f"[yellow]Warning: Could not load dynamic tests: {e}[/yellow]")

    # Also load any remaining individual test files (for backward compatibility)
    for root, dirs, files in os.walk(start_dir):
        for file in files:
            if (
                file.startswith("test_")
                and file.endswith(".py")
                and file
                not in [
                    "test_template.py",
                    "test_brick_mortar.py",
                    "test_warfield.py",
                ]  # Skip old files
            ):
                if test_pattern == "test_*.py" or file == test_pattern:
                    module_name = f"tests.{file[:-3]}"
                    try:
                        module = __import__(module_name, fromlist=[file[:-3]])
                        module_suite = loader.loadTestsFromModule(module)
                        suite.addTest(module_suite)
                    except ImportError as e:
                        console.print(
                            f"[yellow]Warning: Could not import {module_name}: {e}[/yellow]"
                        )
                        continue

    # Count tests
    test_count = suite.countTestCases()

    if test_count == 0:
        console.print(
            f"[yellow]No tests found matching pattern: {test_pattern}[/yellow]"
        )
        return False

    console.print(f"[blue]Running {test_count} tests...[/blue]")

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Display summary
    display_test_summary(result)

    return result.wasSuccessful()


def display_test_summary(result):
    """Display a rich summary of test results"""
    table = Table(title="Test Results Summary")

    table.add_column("Metric", style="bold")
    table.add_column("Count", style="bold")
    table.add_column("Status")

    # Success status
    status = "[green]PASSED[/green]" if result.wasSuccessful() else "[red]FAILED[/red]"

    table.add_row("Total Tests", str(result.testsRun), status)
    table.add_row(
        "Failures",
        str(len(result.failures)),
        "[red]FAILED[/red]" if result.failures else "[green]NONE[/green]",
    )
    table.add_row(
        "Errors",
        str(len(result.errors)),
        "[red]ERROR[/red]" if result.errors else "[green]NONE[/green]",
    )

    console.print(table)

    # Show detailed failures/errors if any
    if result.failures:
        console.print("\n[red]FAILURES:[/red]")
        for test, traceback in result.failures:
            console.print(f"[red]• {test}[/red]")
            console.print(f"[dim]{traceback}[/dim]\n")

    if result.errors:
        console.print("\n[red]ERRORS:[/red]")
        for test, traceback in result.errors:
            console.print(f"[red]• {test}[/red]")
            console.print(f"[dim]{traceback}[/dim]\n")


def run_venue_specific_test(venue_name):
    """Run tests for a specific venue"""
    console.print(f"[blue]Running tests for: {venue_name}[/blue]")

    # Import dynamic tests
    try:
        from tests.dynamic_venue_tests import generated_classes

        # Find the test class for this venue
        target_class = None
        for test_class in generated_classes:
            if (
                hasattr(test_class, "VENUE_NAME")
                and test_class.VENUE_NAME.lower() == venue_name.lower()
            ):
                target_class = test_class
                break

        if target_class is None:
            console.print(f"[red]No test class found for venue: {venue_name}[/red]")
            return False

        # Run tests for this specific class
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(target_class)

        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        display_test_summary(result)
        return result.wasSuccessful()

    except ImportError as e:
        console.print(f"[red]Error loading dynamic tests: {e}[/red]")
        return False


def generate_csv_for_venue(venue_name):
    """Generate CSV test data for a specific venue"""
    console.print(f"[blue]Generating CSV test data for: {venue_name}[/blue]")

    # Find venue config
    venues = get_enabled_venues()
    venue_config = None

    for venue in venues:
        if venue["name"].lower() == venue_name.lower():
            venue_config = venue
            break

    if venue_config is None:
        console.print(f"[red]Venue not found: {venue_name}[/red]")
        return False

    # Import required modules
    from models import Venue
    from storage import Cache

    # Create venue and scraper
    venue = Venue(
        name=venue_config["name"],
        base_url=venue_config["base_url"],
        calendar_path=venue_config["calendar_path"],
    )

    cache = Cache()
    scraper = venue_config["scraper_class"](venue, cache)

    # Scrape events
    with console.status(f"Scraping {venue_name}..."):
        events = scraper.get_events()

    if not events:
        console.print(f"[yellow]No events found for {venue_name}[/yellow]")
        return False

    # Generate CSV filename
    safe_name = venue_config["name"].lower().replace(" ", "_").replace("&", "and")
    csv_file = f"tests/data/{safe_name}_expected.csv"

    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(csv_file), exist_ok=True)

    # Write CSV
    import csv

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "time", "artists", "venue", "url", "cost"])

        for event in events:
            writer.writerow(
                [
                    event.date.strftime("%Y-%m-%d"),
                    event.time.strftime("%H:%M:%S") if event.time else "",
                    ",".join(event.artists),
                    event.venue,
                    event.url or "",
                    event.cost or "",
                ]
            )

    console.print(f"[green]Generated {len(events)} events to {csv_file}[/green]")
    return True


def list_available_tests():
    """List all available venue tests"""
    console.print("[blue]Available venue tests:[/blue]")

    venues = get_enabled_venue_names()
    for i, venue in enumerate(venues, 1):
        console.print(f"  {i}. {venue}")

    console.print(f"\n[dim]Total: {len(venues)} venue tests available[/dim]")
    console.print("\n[dim]Usage examples:[/dim]")
    console.print("  python tests/run_tests.py                    # Run all tests")
    console.print(
        "  python tests/run_tests.py brick_mortar       # Run specific venue tests"
    )
    console.print(
        "  python tests/run_tests.py brick_mortar --generate  # Generate test data"
    )


def main():
    """Main test runner function"""
    if len(sys.argv) == 1:
        # No arguments - run all tests
        discover_and_run_tests()
        return

    if "--list" in sys.argv:
        list_available_tests()
        return

    venue_arg = None
    generate = False

    for arg in sys.argv[1:]:
        if arg == "--generate":
            generate = True
        elif arg != "--list":
            venue_arg = arg

    if venue_arg:
        # Convert venue argument to proper name
        venues = get_enabled_venues()
        venue_name = None

        for venue in venues:
            safe_venue_name = (
                venue["name"]
                .lower()
                .replace(" ", "_")
                .replace("&", "_")
                .replace("-", "_")
            )
            if (
                venue_arg.lower() in safe_venue_name
                or venue_arg.lower().replace("_", " ") in venue["name"].lower()
            ):
                venue_name = venue["name"]
                break

        if venue_name is None:
            console.print(f"[red]Unknown venue: {venue_arg}[/red]")
            console.print("[yellow]Available venues:[/yellow]")
            for venue in venues:
                safe_name = venue["name"].lower().replace(" ", "_").replace("&", "_")
                console.print(f"  {safe_name} -> {venue['name']}")
            return

        if generate:
            generate_csv_for_venue(venue_name)
        else:
            run_venue_specific_test(venue_name)
    else:
        discover_and_run_tests()


if __name__ == "__main__":
    main()
