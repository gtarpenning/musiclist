#!/usr/bin/env python3
"""
Test runner for musiclist project
Usage: python tests/run_tests.py [venue_name]
"""

import sys
import unittest
import os
from rich.console import Console
from rich.table import Table

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

console = Console()


def discover_and_run_tests(test_pattern="test_*.py"):
    """Discover and run tests with rich output"""

    # Discover tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(__file__)

    # First discover all test files
    suite = unittest.TestSuite()
    for root, dirs, files in os.walk(start_dir):
        for file in files:
            if (
                file.startswith("test_")
                and file.endswith(".py")
                and file != "test_template.py"
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
        "[red]✗[/red]" if result.failures else "[green]✓[/green]",
    )
    table.add_row(
        "Errors",
        str(len(result.errors)),
        "[red]✗[/red]" if result.errors else "[green]✓[/green]",
    )
    table.add_row(
        "Skipped",
        str(len(result.skipped)),
        "[yellow]~[/yellow]" if result.skipped else "[green]✓[/green]",
    )

    console.print()
    console.print(table)

    # Show detailed failures if any
    if result.failures:
        console.print("\n[red]Failures:[/red]")
        for test, traceback in result.failures:
            console.print(f"[red]✗ {test}[/red]")
            console.print(traceback)

    if result.errors:
        console.print("\n[red]Errors:[/red]")
        for test, traceback in result.errors:
            console.print(f"[red]✗ {test}[/red]")
            console.print(traceback)


def run_venue_tests(venue_name):
    """Run tests for a specific venue"""
    test_pattern = f"test_{venue_name.lower().replace(' ', '_').replace('&', '')}.py"
    console.print(f"[blue]Running tests for {venue_name}[/blue]")
    console.print(f"Looking for test file: {test_pattern}")
    return discover_and_run_tests(test_pattern)


def list_available_tests():
    """List all available test files"""
    test_dir = os.path.dirname(__file__)
    test_files = [
        f
        for f in os.listdir(test_dir)
        if f.startswith("test_") and f.endswith(".py") and f != "test_template.py"
    ]

    if not test_files:
        console.print("[yellow]No test files found[/yellow]")
        return

    table = Table(title="Available Tests")
    table.add_column("Test File", style="bold")
    table.add_column("Venue", style="green")

    for test_file in sorted(test_files):
        venue_name = (
            test_file.replace("test_", "").replace(".py", "").replace("_", " ").title()
        )
        table.add_row(test_file, venue_name)

    console.print(table)


def generate_csv_for_venue(venue_name):
    """Generate CSV file for a venue by running actual scraper"""
    # Convert venue name to module/class name
    test_pattern = f"test_{venue_name.lower().replace(' ', '_').replace('&', '').replace('-', '_')}.py"

    # Try to find and import the test module
    module_name = f"tests.{test_pattern[:-3]}"
    try:
        module = __import__(module_name, fromlist=[test_pattern[:-3]])

        # Find the test class that inherits from BaseVenueTest
        test_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and hasattr(attr, "VENUE_NAME")
                and hasattr(attr, "SCRAPER_CLASS")
                and attr.VENUE_NAME is not None
            ):  # Exclude base classes
                test_class = attr
                break

        if not test_class:
            console.print(f"[red]Could not find test class for {venue_name}[/red]")
            return False

        # Create an instance and run the scraper
        console.print(f"[blue]Generating CSV for {venue_name}...[/blue]")

        # Create venue and scraper directly to avoid setUp issues
        from models import Venue

        venue = Venue(
            name=test_class.VENUE_NAME,
            base_url=test_class.BASE_URL,
            calendar_path=getattr(test_class, "CALENDAR_PATH", "/calendar/"),
        )
        scraper = test_class.SCRAPER_CLASS(venue)

        # Create test instance for CSV generation
        test_instance = test_class()
        test_instance.venue = venue
        test_instance.scraper = scraper

        if not scraper:
            console.print(f"[red]No scraper configured for {venue_name}[/red]")
            return False

        # Get events from actual scraper
        events = scraper.get_events()
        console.print(f"Found {len(events)} events")

        # Generate CSV
        test_instance.generate_csv_file(events)
        console.print(f"[green]✅ Generated CSV for {venue_name}[/green]")
        return True

    except ImportError as e:
        console.print(f"[red]Could not import test module {module_name}: {e}[/red]")
        return False
    except Exception as e:
        console.print(f"[red]Error generating CSV: {e}[/red]")
        return False


def run_individual_test(venue_name, test_method=None):
    """Run a specific test method for a venue"""
    test_pattern = f"test_{venue_name.lower().replace(' ', '_').replace('&', '').replace('-', '_')}.py"

    if test_method:
        # Run specific test method
        console.print(f"[blue]Running {test_method} for {venue_name}[/blue]")

        # Create test suite with specific method
        loader = unittest.TestLoader()
        module_name = f"tests.{test_pattern[:-3]}"

        try:
            module = __import__(module_name, fromlist=[test_pattern[:-3]])
            # Find test class
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and attr_name.startswith("Test")
                    and hasattr(attr, test_method)
                ):
                    suite = loader.loadTestsFromName(
                        f"{attr_name}.{test_method}", module
                    )
                    break
            else:
                console.print(f"[red]Test method {test_method} not found[/red]")
                return False

        except ImportError as e:
            console.print(f"[red]Could not import test module: {e}[/red]")
            return False
    else:
        # Run all tests for venue
        return run_venue_tests(venue_name)

    # Run the test
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    display_test_summary(result)
    return result.wasSuccessful()


def main():
    """Main test runner"""
    console.print("[bold blue]🎵 Musiclist Test Runner[/bold blue]")

    if len(sys.argv) == 1:
        # Run all tests
        success = discover_and_run_tests()
    elif sys.argv[1] == "--list":
        # List available tests
        list_available_tests()
        return
    elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
        # Show help
        console.print(
            """
[bold]Usage:[/bold]
  python tests/run_tests.py                           # Run all tests
  python tests/run_tests.py brick_mortar              # Run specific venue tests
  python tests/run_tests.py brick_mortar --generate   # Generate CSV from actual scraping
  python tests/run_tests.py brick_mortar test_method  # Run specific test method
  python tests/run_tests.py --list                    # List available tests
  python tests/run_tests.py --help                    # Show this help

[bold]Examples:[/bold]
  python tests/run_tests.py brick_mortar
  python tests/run_tests.py brick_mortar --generate
  python tests/run_tests.py brick_mortar test_csv_data_loads
  python tests/run_tests.py warfield
"""
        )
        return
    else:
        # Parse arguments
        venue_name = sys.argv[1]

        if len(sys.argv) >= 3:
            second_arg = sys.argv[2]
            if second_arg == "--generate":
                success = generate_csv_for_venue(venue_name)
            else:
                # Assume it's a test method name
                success = run_individual_test(venue_name, second_arg)
        else:
            # Run all tests for venue
            success = run_venue_tests(venue_name)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
