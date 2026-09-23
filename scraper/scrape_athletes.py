"""
World Athletics + Wikipedia scraper (best-effort).

Pulls name, country, birth date, and personal bests from public
worldathletics.org athlete profile pages, and career Olympic/World
Championship medal counts from Wikipedia's "Medal record" table, then
writes it all to a JSON file in the schema the Statlete website expects.

Why two sources: World Athletics' own profile page renders its medal
summary (and the fuller "Honours" breakdown) with JavaScript after the
page loads, so a plain HTTP fetch never sees that text at all — no
amount of regex tuning fixes that, since the data simply isn't in the
HTML we receive. Wikipedia's medal-record table, by contrast, is
ordinary server-rendered HTML, so it's a much more reliable source for
this one field. Everything else still comes from World Athletics.

This is still best-effort: if either site changes its markup, the
relevant parse_*() function below will need adjusting. After pulling a
fresh batch, spot-check a couple of athletes you know well.

Be a polite scraper:
- This sleeps between requests (see --delay) — don't set it to 0.
- Check https://worldathletics.org/robots.txt and each site's Terms
  of Use before doing anything beyond a small personal project.
- Don't run this on a schedule or at a scale that could look like
  load-testing their servers.

Usage:
    pip install -r requirements.txt
    python scrape_athletes.py --urls athlete_urls.txt --out data/athletes.json
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
from datetime import datetime

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; StatleteDataCollector/1.0; personal hobby project, not for redistribution)"
}

# Wikimedia's servers are known to reject or rate-limit requests from
# cloud/CI IP ranges (GitHub Actions included) that don't send a
# properly identified User-Agent — see
# https://meta.wikimedia.org/wiki/User-Agent_policy. This is separate
# from HEADERS above since it needs to look like this specific format,
# with a real contact URL, or Wikimedia may still reject it.
WIKI_HEADERS = {
    "User-Agent": "StatleteDataCollector/1.0 (https://github.com/evennorjordet/statlete; personal hobby project, not for redistribution)"
}

STOP_MARKERS = r"Season's bests|SEE MORE|Stay updated"

# Only these two Wikipedia medal-table categories map onto the site's
# current medal fields. Other categories some athletes have (Diamond
# League, Continental Championships, World Indoor Championships) are
# real data too, just not wired into the game yet — see the "Not yet
# implemented" note near the bottom of this file.
WIKI_TRACKED_CATEGORIES = {"Olympic Games": "olympic", "World Championships": "world"}


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def fetch(url, timeout=20):
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def flatten(text):
    """Collapse all whitespace/newlines to single spaces.

    BeautifulSoup's get_text() inserts separators between tags in ways
    that vary depending on the page's exact markup, so relying on an
    exact number of newlines between labels and values is fragile.
    Flattening to one long space-joined string and matching with
    regex across it is far more robust to those layout differences.
    """
    return re.sub(r"\s+", " ", text).strip()


def parse_name_and_country(soup):
    """Try a couple of formats, since not every profile's meta
    description includes a dash-separated event list (retired
    athletes in particular sometimes don't)."""
    meta = soup.find("meta", attrs={"name": "description"})
    desc = meta["content"] if meta and meta.get("content") else ""

    m = re.match(r"^(.*?),\s*(.*?)\s*-\s*(.*)$", desc)
    if m:
        return m.group(1).strip().title(), m.group(2).strip()

    m = re.match(r"^(.*?),\s*(.*)$", desc)
    if m:
        return m.group(1).strip().title(), m.group(2).strip()

    return None, None


def parse_birth_date(flat):
    m = re.search(r"Born\s*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})", flat)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%d %b %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_personal_bests(flat):
    """Find each Result/Date/Score anchor triple and take the event
    name from whatever text sits between the end of the previous
    entry and the start of this one.

    NOTE: this only captures the personal bests World Athletics
    server-renders on the main profile page. Athletes with a long
    history often have more hidden behind the "SEE MORE
    PERFORMANCES" control, which — like the honours widget — appears
    to be filled in by JavaScript rather than present in the initial
    HTML. Getting the complete list would need a tool that actually
    runs the page's JavaScript (e.g. Playwright) rather than a plain
    HTTP fetch. Not implemented yet — see the bottom of this file.
    """
    pbs = []
    start_m = re.search(r"Personal bests", flat)
    if not start_m:
        return pbs

    rest = flat[start_m.end():]
    stop_m = re.search(STOP_MARKERS, rest)
    section = rest[: stop_m.start()] if stop_m else rest

    entry_re = re.compile(
        r"Result\s*([\d:.]+)\s*([A-Z*][A-Z* ]*)?\s*"
        r"Date\s*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s*"
        r"Score\s*(\d+)"
    )
    prev_end = 0
    for m in entry_re.finditer(section):
        event = section[prev_end:m.start()].strip(" -\u2022")
        result, record = m.group(1), (m.group(2) or "").strip()
        try:
            date_iso = datetime.strptime(m.group(3), "%d %b %Y").strftime("%Y-%m-%d")
        except ValueError:
            date_iso = None
        if event:
            pbs.append({
                "event": event,
                "result": result,
                "record": record,
                "score": int(m.group(4)),
                "date": date_iso,
            })
        prev_end = m.end()

    return pbs


def guess_status(pbs):
    years = [int(pb["date"][:4]) for pb in pbs if pb.get("date")]
    if not years:
        return "unknown"
    return "active" if (datetime.now().year - max(years)) <= 2 else "retired"


def parse_profile(html, url):
    soup = BeautifulSoup(html, "html.parser")
    flat = flatten(soup.get_text(" "))

    name, country = parse_name_and_country(soup)
    if not name:
        raise ValueError(f"Could not find a name/country on {url} — page layout may have changed.")

    pbs = parse_personal_bests(flat)
    # The meta description's event order isn't reliably the athlete's
    # specialty (it can shift with recent results), so use whichever
    # personal best scores highest instead — a much more reliable
    # signal of their main event.
    primary_event = max(pbs, key=lambda p: p["score"])["event"] if pbs else None

    return {
        "id": slugify(name),
        "name": name,
        "country": country,
        "birth_date": parse_birth_date(flat),
        "primary_event": primary_event,
        "medals": {"olympic_gold": 0, "olympic_silver": 0, "olympic_bronze": 0,
                   "world_gold": 0, "world_silver": 0, "world_bronze": 0},
        "status": guess_status(pbs),
        "personal_bests": pbs,
        "profile_url": url,
    }


def find_wikipedia_title(name):
    """Look up the most likely Wikipedia article for an athlete by
    name, using Wikipedia's own opensearch API (no scraping needed
    for this step — it's a public, documented JSON endpoint)."""
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "opensearch", "search": name, "limit": 1, "format": "json"},
            headers=WIKI_HEADERS, timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        titles = data[1] if len(data) > 1 else []
        if not titles:
            print(f"    wikipedia: opensearch returned no title for '{name}'", file=sys.stderr)
        return titles[0] if titles else None
    except requests.RequestException as exc:
        print(f"    wikipedia: opensearch request failed ({exc})", file=sys.stderr)
        return None
    except (ValueError, IndexError) as exc:
        print(f"    wikipedia: opensearch response was unexpected ({exc})", file=sys.stderr)
        return None


def parse_wikipedia_medals(html):
    """Parse Wikipedia's standard 'Medal record' infobox table.

    Structure: a heading with id="Medal_record", followed by a table
    where single-cell rows are section headers (competition name, or
    filler like "Representing Norway") and multi-cell rows are medal
    entries: [place text, year + venue, event].

    This is based on the medal-table template Wikipedia uses across
    most Olympic-sport athlete pages, not verified against this exact
    account's HTML — if it comes back all zero for someone you know
    has medals, that's the first thing to check by hand.
    """
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find(id="Medal_record")
    if not heading:
        return None

    table = None
    for el in heading.parent.find_all_next():
        if el.name == "table":
            table = el
            break
        if el.name in ("h2", "h3"):
            break
    if table is None:
        return None

    medals = {"olympic_gold": 0, "olympic_silver": 0, "olympic_bronze": 0,
              "world_gold": 0, "world_silver": 0, "world_bronze": 0}
    current = None

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        texts = [c.get_text(" ", strip=True) for c in cells]
        if len(cells) <= 1:
            label = texts[0] if texts else ""
            current = WIKI_TRACKED_CATEGORIES.get(label)  # None for untracked/filler rows
            continue
        if current and texts:
            m = re.match(r"(Gold|Silver|Bronze) medal", texts[0])
            if m:
                bucket = f"{current}_{m.group(1).lower()}"
                medals[bucket] = medals.get(bucket, 0) + 1

    return medals


def fetch_medals_from_wikipedia(name):
    title = find_wikipedia_title(name)
    if not title:
        return None
    url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
    try:
        resp = requests.get(url, headers=WIKI_HEADERS, timeout=20)
        resp.raise_for_status()
        html = resp.text
    except requests.RequestException as exc:
        print(f"    wikipedia: failed to fetch page '{title}' ({exc})", file=sys.stderr)
        return None
    medals = parse_wikipedia_medals(html)
    if medals is None:
        print(f"    wikipedia: fetched '{title}' but found no Medal_record section", file=sys.stderr)
    return medals


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--urls", required=True, help="Text file with one worldathletics.org profile URL per line")
    ap.add_argument("--out", required=True, help="Path to write the resulting JSON file")
    ap.add_argument("--delay", type=float, default=3.0, help="Seconds to wait between requests (default 3)")
    ap.add_argument("--skip-wikipedia", action="store_true", help="Skip the Wikipedia medal lookup (faster, no medal data)")
    args = ap.parse_args()

    with open(args.urls) as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    athletes = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}", file=sys.stderr)
        try:
            html = fetch(url)
            profile = parse_profile(html, url)
            if not profile["personal_bests"]:
                print(f"  warning: no personal bests parsed for {profile['name']} — check manually", file=sys.stderr)

            if not args.skip_wikipedia:
                time.sleep(args.delay)
                medals = fetch_medals_from_wikipedia(profile["name"])
                if medals is not None:
                    profile["medals"] = medals
                else:
                    print(f"  note: no Wikipedia medal table found for {profile['name']} (left at 0)", file=sys.stderr)

            athletes.append(profile)
        except Exception as exc:
            print(f"  skipped: {exc}", file=sys.stderr)
        if i < len(urls):
            time.sleep(args.delay)

    out = {
        "source_note": "Personal bests and birth dates scraped from worldathletics.org; Olympic/World Championship medal counts from Wikipedia's medal-record table. 'status' is a rough active/retired guess based on how recent the most recent personal best is — check it by hand.",
        "athletes": athletes,
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(athletes)} athletes to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()

# --- Not yet implemented (requested, tracked for later) ---
#
# 1. Full honours breakdown (Diamond League, Continental, World Indoor
#    medals) straight from World Athletics' own honours widget. That
#    widget is JavaScript-rendered, so this needs a headless-browser
#    tool (e.g. Playwright) instead of requests+BeautifulSoup — a
#    bigger change than a parsing tweak.
#
# 2. ALL personal bests, not just the ones server-rendered on the main
#    profile page. The "SEE MORE PERFORMANCES" expansion looks like
#    the same JS-rendering situation as #1 and likely needs the same
#    fix.
#
# 3. Scraping every athlete with a World Athletics profile, or as a
#    fallback, the top 100 from each event's world ranking list. Not
#    attempted yet — would mean crawling ranking list pages per event,
#    de-duplicating athlete URLs across events, and scraping each one,
#    which is a much larger and slower job than the current
#    hand-picked URL list.
