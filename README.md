# Musiclist

Multi-venue music event scraper for San Francisco.

<img width="1006" height="770" alt="cal" src="https://github.com/user-attachments/assets/21fdbe58-750b-474e-a623-557c9f027281" />

<img width="599" height="348" alt="venue" src="https://github.com/user-attachments/assets/a2e352e8-72ea-4366-9fb6-e52295858e7d" />



## Install
```bash
pip install sf-music-calendar
```

Use Python 3.12 or newer: some venue sites sit behind Cloudflare, which
rejects the OpenSSL 1.1 TLS stack older Pythons ship with (`music doctor`
says so when it happens).


## Usage
```bash
music                 # Events for this month + next
music kilowatt        # One venue (fuzzy: "music great american", "music cafe du nord")
music pin 5           # Pin event #5 (or: music pin "Artist Name")
music star rickshaw   # Star a venue; "music starred" shows only starred venues
music scrape          # Every upcoming show, freshly fetched
music doctor          # Live-check every scraper, exits 1 if one broke
music --help          # Full options
```

Data (events, pins, stars, page cache) lives in `~/.musiclist`; set
`MUSICLIST_HOME` to put it elsewhere. Venues refresh at most once a day.

## Venues

27 venues, most read through the ticketing platform the venue's own site uses:

| Platform | Venues |
| --- | --- |
| TicketWeb plugin | The Independent, August Hall, Brick & Mortar, Neck of the Woods, Bimbo's 365 Club |
| SeeTickets plugin | The Chapel, Rickshaw Stop, Hotel Utah Saloon, Great American Music Hall |
| schema.org JSON-LD | The Fillmore, The Masonic, The Midway |
| DICE widget | Kilowatt, The Knockout, Halcyon |
| Venue sites | Café du Nord, Swedish American Hall, Bill Graham Civic, The Warfield, The Regency Ballroom, Bottom of the Hill, Public Works, 1015 Folsom, DNA Lounge, Audio, Boom Boom Room, Gray Area |

## Website

The same listings as a static page: **https://sf-music-calendar.pages.dev**. Search, a
when filter (tonight, weekend, or a day picked from a calendar), and a venue picker;
the filters live in the URL, so a view can be bookmarked or shared.

A LaunchAgent on the Mac rebuilds and redeploys it every Sunday at 9:00:

```bash
site/install-weekly.sh                              # install or update (tracks main)
launchctl kickstart gui/$(id -u)/local.musiclist-site   # run it now
tail -f ~/.musiclist-site/weekly.log
site/install-weekly.sh --uninstall
```

Working on the page itself:

```bash
python site/build.py              # scrape every venue into ~/.musiclist-site, write site/dist/
python site/build.py --no-scrape  # rebuild from the last scrape
python -m http.server -d site/dist 8791
python site/build.py --deploy     # publish (refuses if the scrape looks broken)
```

## Development
```bash
pip install -e .

make test         # Offline tests (parsers run on fixtures, no network)
music doctor      # The live check: did any venue's site change?
make format       # Format code
```

Adding a venue on a platform above is a single entry in `venues_config.py`
pointing at the shared scraper; see `LLM_CONTEXT.md`.
