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

For each athlete: name, country, birth date, career Olympic/World
Championship medal counts, and every personal best listed on their
profile (event, result, any record tag like WR/AR/NR, points score,
and date).

## Known limitations

- **No official API.** This reads rendered page text, so it breaks
  if World Athletics changes their page layout. If a run comes back
  empty or looks wrong, open one profile URL in a browser, view
  source, and compare it against what `parse_profile()` in
  `scrape_athletes.py` expects — the section comments explain what
  each part is looking for.
- **`status` (active/retired) is a guess**, based on whether the
  athlete's most recent personal best is within the last two years.
  It has no way to know about injuries, retirement announcements, or
  athletes who compete rarely — check it by hand for anyone it
  matters for.
- **Medal counts only cover Olympic Games and World Championships**,
  since those are the two title types called out clearly on the
  profile page. Continental, indoor, and Diamond League titles
  aren't included.
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
