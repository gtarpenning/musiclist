#!/usr/bin/env python3
"""Build the SF Shows website from a fresh scrape, and optionally deploy it.

    python site/build.py                 # scrape every venue, write site/dist/
    python site/build.py --no-scrape     # rebuild from the last scrape (styling work)
    python site/build.py --deploy        # ... then publish to Cloudflare Pages

Data lives in its own MUSICLIST_HOME (default ~/.musiclist-site) so the
weekly job never touches your personal pins and stars. A venue that fails
to load keeps last week's listings (the DB only prunes on a successful
scrape) and is marked stale on the page. If too much of the scrape fails,
nothing is deployed and the live site keeps the previous build.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("MUSICLIST_HOME", str(Path.home() / ".musiclist-site"))

from storage import Cache, Database  # noqa: E402
from utils.parallel import refresh_venue  # noqa: E402
from venues_config import DEFAULT_MAX_WORKERS, get_venues_config  # noqa: E402

PROJECT = "sf-music-calendar"  # Cloudflare Pages project -> https://sf-music-calendar.pages.dev
MIN_OK_SHARE = 0.6  # deploy only if at least this share of venues scraped fine...
MIN_EVENTS = 150  # ...and at least this many upcoming shows exist
RETRY_PAUSE = 15  # seconds to let rate limits cool before retrying failed venues


def log(msg: str) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def scrape(configs, db: Database) -> dict:
    """Refresh every venue in parallel, logging each one as it finishes."""
    started = time.time()
    results = {}
    with ThreadPoolExecutor(max_workers=DEFAULT_MAX_WORKERS) as pool:
        futures = {
            pool.submit(refresh_venue, cfg, db, Cache(), True): cfg["name"]
            for cfg in configs
        }
        for done, future in enumerate(as_completed(futures), 1):
            name = futures[future]
            r = future.result()
            results[name] = r
            elapsed = time.time() - started
            eta = elapsed / done * (len(configs) - done)
            log(
                f"[{done}/{len(configs)}] {name}: {describe(r)} ({r.elapsed:.1f}s) elapsed {elapsed:.0f}s eta {eta:.0f}s"
            )

    # Cloudflare-fronted venues sometimes 403 a burst of parallel requests but
    # pass a lone one, so give failures a second, sequential try.
    failed = [
        cfg for cfg in configs if results[cfg["name"]].status not in ("fresh", "cached")
    ]
    if failed:
        time.sleep(RETRY_PAUSE)
    for n, cfg in enumerate(failed, 1):
        r = refresh_venue(cfg, db, Cache(), True)
        results[cfg["name"]] = r
        log(
            f"[retry {n}/{len(failed)}] {cfg['name']}: {describe(r)} ({r.elapsed:.1f}s)"
        )
    return results


def describe(r) -> str:
    return (
        f"{r.count} shows"
        if r.status == "fresh"
        else f"{r.status.upper()} {r.error or 'nothing parsed'}"
    )


def price(cost):
    """Tidy a scraped price for display: "$25.00 - $30.00" -> "$25–$30", "$0.00" -> "free"."""
    if not cost or not cost.strip():
        return None
    c = re.sub(r"(\d)\.00\b", r"\1", cost.strip())
    c = re.sub(r"(?<=\d)\s*-\s*(?=\$?\d)", "–", c)
    if re.fullmatch(r"(\$0(–\$?0)?|free)", c, re.I):
        return "free"
    return c


def export(configs, db: Database, results) -> dict:
    names = [c["name"] for c in configs]
    index = {name: i for i, name in enumerate(names)}
    events = db.get_events(venues=names)  # upcoming only, ordered by date, time

    counts = {}
    for e in events:
        counts[e.venue] = counts.get(e.venue, 0) + 1

    venues = []
    for cfg in configs:
        r = results.get(cfg["name"]) if results else None
        last = db.get_last_scraped(cfg["name"])
        venues.append(
            {
                "name": cfg["name"],
                "area": cfg.get("area", ""),
                "url": cfg["base_url"].rstrip("/") + cfg.get("calendar_path", "/"),
                "shows": counts.get(cfg["name"], 0),
                # stale: this run couldn't refresh it, so its rows are from an earlier scrape
                "stale": bool(r and r.status not in ("fresh", "cached")),
                "checked": last.isoformat(timespec="minutes") if last else None,
            }
        )

    return {
        "generated": datetime.now().astimezone().isoformat(timespec="minutes"),
        "venues": venues,
        "events": [
            {
                "date": e.date.isoformat(),
                "time": e.time.strftime("%H:%M") if e.time else None,
                "artists": e.artists,
                "venue": index[e.venue],
                "url": e.url,
                "price": price(e.cost),
            }
            for e in events
            if e.venue in index
        ],
    }


def write_dist(data: dict) -> Path:
    dist = SITE / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    shutil.copytree(SITE / "public", dist)
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    (dist / "events.json").write_text(payload, encoding="utf-8")

    # Cache-bust assets and listings by content, so a deploy is never half-cached.
    # app.js reads the version back off its own <script src> to fetch events.json.
    version = hashlib.sha1(
        b"".join(
            (dist / f).read_bytes()
            for f in ("app.js", "site.css", "typewriter.css", "events.json")
        )
    ).hexdigest()[:10]
    index = dist / "index.html"
    index.write_text(
        index.read_text(encoding="utf-8").replace("__VERSION__", version),
        encoding="utf-8",
    )
    return dist


def deploy(dist: Path) -> None:
    npx = shutil.which("npx") or "/opt/homebrew/bin/npx"
    cmd = [
        npx, "--yes", "wrangler@4", "pages", "deploy", str(dist),
        "--project-name", PROJECT, "--branch", "main",
        "--commit-dirty=true", "--commit-message", f"weekly build {datetime.now():%Y-%m-%d}",
    ]  # fmt: skip
    log("deploying: " + " ".join(cmd[1:5]) + f" --project-name {PROJECT}")
    # wrangler keeps a .wrangler/ cache in its cwd; launchd jobs start in "/", which isn't writable
    subprocess.run(cmd, check=True, cwd=SITE)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--no-scrape", action="store_true", help="reuse the last scrape"
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="publish to Cloudflare Pages after building",
    )
    args = parser.parse_args()

    configs = get_venues_config()
    db = Database()
    log(f"data dir {os.environ['MUSICLIST_HOME']}, {len(configs)} venues")

    results = {}
    if not args.no_scrape:
        results = scrape(configs, db)
    data = export(configs, db, results)

    ok = sum(1 for v in data["venues"] if not v["stale"])
    log(f"{len(data['events'])} upcoming shows, {ok}/{len(configs)} venues refreshed")
    dist = write_dist(data)
    log(
        f"wrote {dist} ({(dist / 'events.json').stat().st_size // 1024} KB of listings)"
    )

    if args.deploy:
        if ok < MIN_OK_SHARE * len(configs) or len(data["events"]) < MIN_EVENTS:
            log(
                "NOT deploying: scrape looks broken, the live site keeps last week's build"
            )
            return 1
        deploy(dist)
        log(f"live at https://{PROJECT}.pages.dev")
    return 0


if __name__ == "__main__":
    sys.exit(main())
