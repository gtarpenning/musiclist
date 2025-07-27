#!/usr/bin/env python3
"""
Benchmark script for musiclist scrapers.

Times each scraper, collects performance metrics, and generates a detailed report.
"""

import time
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from rich.console import Console
from rich.table import Table
from rich.status import Status
from rich.panel import Panel
from rich import box

# Add project root to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from venues_config import VENUES_CONFIG
from models.venue import Venue
from storage.cache import Cache
from utils.parallel import ParallelScraper


@dataclass
class BenchmarkResult:
    venue_name: str
    success: bool
    duration_seconds: float
    event_count: int
    error_message: str = ""
    url: str = ""
    cache_hit: bool = False


@dataclass
class ParallelBenchmarkResult:
    worker_count: int
    duration_seconds: float
    total_events: int
    venues_scraped: int
    success: bool
    error_message: str = ""


class ScraperBenchmark:
    def __init__(
        self,
        benchmark_parallel: bool = False,
        parallel_workers: Optional[List[int]] = None,
    ):
        self.console = Console()
        self.results: List[BenchmarkResult] = []
        self.parallel_results: List[ParallelBenchmarkResult] = []
        self.benchmark_parallel = benchmark_parallel
        self.parallel_workers = parallel_workers or [1, 2, 4, 6, 8, 10]
        # Disable caching for accurate benchmark timing
        self.cache = None

    def benchmark_scraper(self, venue_config: Dict[str, Any]) -> BenchmarkResult:
        """Benchmark a single scraper"""
        venue_name = venue_config["name"]
        scraper_class = venue_config["scraper_class"]

        # Create venue object
        venue = Venue(
            name=venue_name,
            base_url=venue_config["base_url"],
            calendar_path=venue_config["calendar_path"],
        )

        # Initialize scraper without cache for accurate timing
        scraper = scraper_class(venue, cache=None)

        try:
            # Record start time
            start_time = time.time()

            # Run the scraper
            events = scraper.get_events()

            # Calculate duration
            duration = time.time() - start_time

            return BenchmarkResult(
                venue_name=venue_name,
                success=True,
                duration_seconds=duration,
                event_count=len(events),
                url=venue.calendar_url,
            )

        except Exception as e:
            duration = time.time() - start_time
            return BenchmarkResult(
                venue_name=venue_name,
                success=False,
                duration_seconds=duration,
                event_count=0,
                error_message=str(e),
                url=venue.calendar_url,
            )

    def run_benchmarks(self):
        """Run benchmarks for all scrapers"""
        self.console.print(
            Panel(
                "[bold blue]🎵 Musiclist Scraper Benchmark[/bold blue]\n"
                f"Testing {len(VENUES_CONFIG)} venue scrapers...",
                box=box.ROUNDED,
            )
        )
        self.console.print()

        for i, venue_config in enumerate(VENUES_CONFIG, 1):
            venue_name = venue_config["name"]

            # Show current progress without progress bar
            self.console.print(
                f"[dim]({i}/{len(VENUES_CONFIG)})[/dim] Testing [cyan]{venue_name}[/cyan]..."
            )

            result = self.benchmark_scraper(venue_config)
            self.results.append(result)

            # Show immediate feedback
            status = "✅" if result.success else "❌"
            duration_color = (
                "red"
                if result.duration_seconds > 2
                else "yellow" if result.duration_seconds > 1 else "green"
            )
            self.console.print(
                f"    {status} [{duration_color}]{result.duration_seconds:.2f}s[/{duration_color}] ({result.event_count} events)"
            )

        self.console.print()

    def display_results(self):
        """Display benchmark results in a nice table"""
        # Sort results by duration (slowest first)
        sorted_results = sorted(
            self.results, key=lambda r: r.duration_seconds, reverse=True
        )

        # Create results table
        table = Table(title="📊 Scraper Performance Results", box=box.ROUNDED)
        table.add_column("Rank", style="bold", width=6)
        table.add_column("Venue", style="cyan", min_width=25)
        table.add_column("Status", justify="center", width=8)
        table.add_column("Time (s)", justify="right", style="yellow", width=10)
        table.add_column("Events", justify="right", style="green", width=8)
        table.add_column("Error", style="red", max_width=30)

        for i, result in enumerate(sorted_results, 1):
            status = "✅ Pass" if result.success else "❌ Fail"
            error_display = (
                result.error_message[:30] + "..."
                if len(result.error_message) > 30
                else result.error_message
            )

            # Color code the time based on performance
            time_str = f"{result.duration_seconds:.2f}"
            if result.duration_seconds > 10:
                time_color = "red"
            elif result.duration_seconds > 5:
                time_color = "yellow"
            else:
                time_color = "green"

            table.add_row(
                str(i),
                result.venue_name,
                status,
                f"[{time_color}]{time_str}[/{time_color}]",
                str(result.event_count) if result.success else "0",
                error_display if not result.success else "",
            )

        self.console.print(table)

        # Display summary statistics
        successful_results = [r for r in self.results if r.success]
        failed_results = [r for r in self.results if not r.success]

        if successful_results:
            avg_time = sum(r.duration_seconds for r in successful_results) / len(
                successful_results
            )
            total_events = sum(r.event_count for r in successful_results)
            fastest = min(successful_results, key=lambda r: r.duration_seconds)
            slowest = max(successful_results, key=lambda r: r.duration_seconds)
        else:
            avg_time = 0
            total_events = 0
            fastest = None
            slowest = None

        summary = Panel(
            f"[bold]Summary Statistics[/bold]\n\n"
            f"✅ Successful: {len(successful_results)}/{len(self.results)}\n"
            f"❌ Failed: {len(failed_results)}/{len(self.results)}\n"
            f"📊 Average time: {avg_time:.2f}s\n"
            f"🎵 Total events found: {total_events}\n"
            + (
                f"🚀 Fastest: {fastest.venue_name} ({fastest.duration_seconds:.2f}s)\n"
                if fastest
                else ""
            )
            + (
                f"🐌 Slowest: {slowest.venue_name} ({slowest.duration_seconds:.2f}s)"
                if slowest
                else ""
            ),
            title="Benchmark Summary",
            box=box.ROUNDED,
        )

        self.console.print(summary)

    def generate_report(self):
        """Generate detailed JSON report file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"benchmarking/benchmark_report_{timestamp}.json"

        # Calculate summary stats
        successful_results = [r for r in self.results if r.success]
        failed_results = [r for r in self.results if not r.success]

        report_data = {
            "benchmark_info": {
                "timestamp": datetime.now().isoformat(),
                "total_venues": len(VENUES_CONFIG),
                "python_version": sys.version,
                "benchmark_type": (
                    "parallel" if self.benchmark_parallel else "individual"
                ),
            }
        }

        if self.benchmark_parallel:
            # Parallel benchmark report
            successful_parallel = [r for r in self.parallel_results if r.success]
            report_data.update(
                {
                    "parallel_summary": {
                        "successful_runs": len(successful_parallel),
                        "worker_counts_tested": self.parallel_workers,
                        "average_time_seconds": (
                            sum(r.duration_seconds for r in successful_parallel)
                            / len(successful_parallel)
                            if successful_parallel
                            else 0
                        ),
                    },
                    "parallel_results": [
                        asdict(result)
                        for result in sorted(
                            self.parallel_results, key=lambda r: r.duration_seconds
                        )
                    ],
                }
            )
        else:
            # Individual scraper report
            successful_results = [r for r in self.results if r.success]
            failed_results = [r for r in self.results if not r.success]

            report_data.update(
                {
                    "summary": {
                        "successful_scrapers": len(successful_results),
                        "failed_scrapers": len(failed_results),
                        "success_rate": len(successful_results)
                        / len(self.results)
                        * 100,
                        "average_time_seconds": (
                            sum(r.duration_seconds for r in successful_results)
                            / len(successful_results)
                            if successful_results
                            else 0
                        ),
                        "total_events_found": sum(
                            r.event_count for r in successful_results
                        ),
                    },
                    "results": [
                        asdict(result)
                        for result in sorted(
                            self.results, key=lambda r: r.duration_seconds, reverse=True
                        )
                    ],
                    "failures": [
                        {
                            "venue": result.venue_name,
                            "error": result.error_message,
                            "url": result.url,
                        }
                        for result in failed_results
                    ],
                }
            )

        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        self.console.print(
            f"\n📄 Detailed report saved to: [bold cyan]{report_file}[/bold cyan]"
        )
        return report_file

    def benchmark_parallel_scraper(self, worker_count: int) -> ParallelBenchmarkResult:
        """Benchmark the parallel scraper with different worker counts"""
        try:
            # Clear any existing cache to ensure fresh scraping
            from storage.database import Database

            db = Database()

            # Record start time
            start_time = time.time()

            # Create parallel scraper with specific worker count
            parallel_scraper = ParallelScraper(max_workers=worker_count)

            # Run parallel scraping (force refresh to bypass cache)
            all_events, venue_stats = parallel_scraper.scrape_venues_parallel(
                VENUES_CONFIG, force_refresh=True
            )

            # Calculate duration
            duration = time.time() - start_time

            return ParallelBenchmarkResult(
                worker_count=worker_count,
                duration_seconds=duration,
                total_events=len(all_events),
                venues_scraped=len([v for v in venue_stats.values() if v >= 0]),
                success=True,
            )

        except Exception as e:
            duration = time.time() - start_time
            return ParallelBenchmarkResult(
                worker_count=worker_count,
                duration_seconds=duration,
                total_events=0,
                venues_scraped=0,
                success=False,
                error_message=str(e),
            )

    def run_parallel_benchmarks(self):
        """Run benchmarks for different parallelism settings"""
        self.console.print(
            Panel(
                "[bold green]⚡ Parallel Scraper Benchmark[/bold green]\n"
                f"Testing parallel scraping with {len(self.parallel_workers)} different worker counts...\n"
                f"Workers to test: {', '.join(map(str, self.parallel_workers))}",
                box=box.ROUNDED,
            )
        )
        self.console.print()

        for i, worker_count in enumerate(self.parallel_workers, 1):
            self.console.print(
                f"[dim]({i}/{len(self.parallel_workers)})[/dim] Testing with [cyan]{worker_count} workers[/cyan]..."
            )

            result = self.benchmark_parallel_scraper(worker_count)
            self.parallel_results.append(result)

            # Show immediate feedback
            status = "✅" if result.success else "❌"
            duration_color = (
                "red"
                if result.duration_seconds > 10
                else "yellow" if result.duration_seconds > 5 else "green"
            )
            self.console.print(
                f"    {status} [{duration_color}]{result.duration_seconds:.2f}s[/{duration_color}] ({result.total_events} events, {result.venues_scraped} venues)"
            )

        self.console.print()

    def display_parallel_results(self):
        """Display parallel benchmark results"""
        if not self.parallel_results:
            return

        # Sort results by duration (fastest first for parallel)
        sorted_results = sorted(self.parallel_results, key=lambda r: r.duration_seconds)

        # Create parallel results table
        table = Table(title="⚡ Parallel Scraper Performance Results", box=box.ROUNDED)
        table.add_column("Rank", style="bold", width=6)
        table.add_column("Workers", style="cyan", width=10)
        table.add_column("Status", justify="center", width=8)
        table.add_column("Time (s)", justify="right", style="yellow", width=10)
        table.add_column("Events", justify="right", style="green", width=8)
        table.add_column("Venues", justify="right", style="blue", width=8)
        table.add_column("Error", style="red", max_width=25)

        for i, result in enumerate(sorted_results, 1):
            status = "✅ Pass" if result.success else "❌ Fail"
            error_display = (
                result.error_message[:25] + "..."
                if len(result.error_message) > 25
                else result.error_message
            )

            # Color code the time based on performance
            time_str = f"{result.duration_seconds:.2f}"
            if result.duration_seconds > 10:
                time_color = "red"
            elif result.duration_seconds > 5:
                time_color = "yellow"
            else:
                time_color = "green"

            table.add_row(
                str(i),
                str(result.worker_count),
                status,
                f"[{time_color}]{time_str}[/{time_color}]",
                str(result.total_events) if result.success else "0",
                str(result.venues_scraped) if result.success else "0",
                error_display if not result.success else "",
            )

        self.console.print(table)

        # Display parallel summary statistics
        successful_results = [r for r in self.parallel_results if r.success]

        if successful_results:
            fastest = min(successful_results, key=lambda r: r.duration_seconds)
            slowest = max(successful_results, key=lambda r: r.duration_seconds)
            avg_time = sum(r.duration_seconds for r in successful_results) / len(
                successful_results
            )

            # Calculate speedup
            single_worker_result = next(
                (r for r in successful_results if r.worker_count == 1), None
            )
            if single_worker_result and fastest.worker_count != 1:
                speedup = (
                    single_worker_result.duration_seconds / fastest.duration_seconds
                )
                speedup_text = f"🚀 Best speedup: {speedup:.1f}x (1 → {fastest.worker_count} workers)\n"
            else:
                speedup_text = ""
        else:
            fastest = slowest = None
            avg_time = 0
            speedup_text = ""

        summary = Panel(
            f"[bold]Parallel Benchmark Summary[/bold]\n\n"
            f"✅ Successful: {len(successful_results)}/{len(self.parallel_results)}\n"
            f"📊 Average time: {avg_time:.2f}s\n"
            + (
                f"🏆 Fastest: {fastest.worker_count} workers ({fastest.duration_seconds:.2f}s)\n"
                if fastest
                else ""
            )
            + (
                f"🐌 Slowest: {slowest.worker_count} workers ({slowest.duration_seconds:.2f}s)\n"
                if slowest
                else ""
            )
            + speedup_text,
            title="Parallel Performance Summary",
            box=box.ROUNDED,
        )

        self.console.print(summary)

    def run(self):
        """Run the complete benchmark suite"""
        start_time = time.time()

        try:
            if self.benchmark_parallel:
                self.run_parallel_benchmarks()
                self.display_parallel_results()
            else:
                self.run_benchmarks()
                self.display_results()

            report_file = self.generate_report()

            total_time = time.time() - start_time
            self.console.print(f"\n🎯 Benchmark completed in {total_time:.2f} seconds")

        except KeyboardInterrupt:
            self.console.print("\n❌ Benchmark interrupted by user")
            sys.exit(1)
        except Exception as e:
            self.console.print(f"\n💥 Benchmark failed with error: {e}")
            sys.exit(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Benchmark musiclist scrapers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Benchmark individual scrapers
  %(prog)s --parallel                         # Benchmark parallel scraping with default worker counts
  %(prog)s --parallel --workers 1,2,4,8      # Benchmark parallel scraping with custom worker counts
        """,
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Benchmark parallel scraping performance instead of individual scrapers",
    )

    parser.add_argument(
        "--workers",
        type=str,
        help="Comma-separated list of worker counts to test (e.g., '1,2,4,8'). Default: 1,2,4,6,8,10",
    )

    args = parser.parse_args()

    # Parse worker counts if provided
    parallel_workers = None
    if args.workers:
        try:
            parallel_workers = [int(w.strip()) for w in args.workers.split(",")]
        except ValueError:
            print(
                "Error: Invalid worker counts. Use comma-separated integers (e.g., '1,2,4,8')"
            )
            sys.exit(1)

    benchmark = ScraperBenchmark(
        benchmark_parallel=args.parallel, parallel_workers=parallel_workers
    )
    benchmark.run()


if __name__ == "__main__":
    main()
