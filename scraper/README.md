# Statlete scraper

A best-effort scraper for worldathletics.org athlete profile pages.
World Athletics doesn't publish a public API, so this fetches the
same profile pages a browser would load and pulls the visible text
apart with a few regular expressions.

## Setup

```
pip install -r requirements.txt
```

## Usage

```
python scrape_athletes.py --urls athlete_urls.txt --out data/athletes.json
```

- `athlete_urls.txt` is a plain list of profile URLs, one per line
  (a starter list matching the demo roster is included). Add more by
  searching "`<athlete name>` worldathletics.org" or browsing
  [worldathletics.org/athletes](https://worldathletics.org/athletes)
  and copying the profile link.
- `--out` is where the resulting JSON gets written. Point it at the
  website's `data/athletes.json` to feed the game directly.
- `--delay` (default 3 seconds) controls the pause between requests.

## What it extracts

For each athlete: name, country, birth date, and every personal best
listed on their World Athletics profile page (event, result, any
record tag like WR/AR/NR, points score, and date). Career Olympic and
World Championship medal counts come from Wikipedia's "Medal record"
table instead — see below for why.

## Known limitations

- **No official API**, for either site. This reads rendered page
  text/HTML, so it breaks if either site changes its markup.
- **World Athletics' own medal/honours display doesn't work with a
  plain fetch at all.** Its summary badges (and the fuller "Honours"
  breakdown you can view on a profile page) are filled in by
  JavaScript after the page loads — a plain HTTP request never
  receives that content, no matter how the parsing regex is written.
  That's why medals come from Wikipedia's medal-record table instead,
  which is ordinary static HTML. Wikipedia won't have a table for
  every athlete (younger or less decorated ones often don't), in
  which case medals are left at 0 — check by hand if that matters for
  someone specific. Pass `--skip-wikipedia` to skip this step
  entirely (faster, no medal data).
- **Personal bests are also incomplete for athletes with a long
  history.** The profile page only server-renders a handful of bests;
  the rest sit behind a "SEE MORE PERFORMANCES" control that appears
  to be the same JavaScript-rendering situation as the honours
  widget. Getting the full list would need a tool that actually runs
  the page's JavaScript (e.g. Playwright) rather than a plain fetch —
  not implemented yet.
- **`status` (active/retired) is a guess**, based on whether the
  athlete's most recent personal best is within the last two years.
  It has no way to know about injuries, retirement announcements, or
  athletes who compete rarely — check it by hand for anyone it
  matters for.
- **Some athletes won't parse cleanly** — profiles for field-event
  specialists, multi-eventers, or anyone with unusual formatting may
  need the parsing rules adjusted. The script prints a "skipped"
  message with the reason rather than crashing.

## Etiquette

- Keep `--delay` at a few seconds; don't hammer their servers.
- Check [worldathletics.org/robots.txt](https://worldathletics.org/robots.txt)
  and their [Terms and Conditions](https://www.worldathletics.org/terms-and-conditions)
  before scraping beyond a small personal project.
- This is meant for a hobby project's worth of athletes (tens, not
  thousands). If you want a full database, look into whether World
  Athletics offers any data licensing before scraping at scale.
