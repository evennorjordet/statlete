"""
World Athletics profile scraper (best-effort).

Pulls name, country, birth date, career medal counts, and personal
bests from public worldathletics.org athlete profile pages, and
writes them to a JSON file in the schema the Statlete website expects.

There is no official public API for this data, so this reads the
same text a browser would see on the profile page. That makes it
fragile: if World Athletics changes the page layout, the parsing in
parse_profile() below will need adjusting. After pulling a fresh
batch, spot-check a couple of athletes you know well before trusting
the rest.

Be a polite scraper:
- This sleeps between requests (see --delay) — don't set it to 0.
- Check https://worldathletics.org/robots.txt and the site's Terms
  of Use before doing anything beyond a small personal project.
- Don't run this on a schedule or at a scale that could look like
  load-testing their site.

Usage:
    pip install -r requirements.txt
    python scrape_athletes.py --urls athlete_urls.txt --out data/athletes.json
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; StatleteDataCollector/1.0; personal hobby project, not for redistribution)"
}

# World Athletics profile pages list championship titles as a count
# immediately followed by a label, e.g. "3X" + "World champion". This
# maps the labels we care about to buckets in the output schema.
TITLE_TO_BUCKET = {
    "Olympic champion": "olympic_gold",
    "Olympic Games silver medallist": "olympic_silver",
    "Olympic Games bronze medallist": "olympic_bronze",
    "World champion": "world_gold",
    "World Championships silver medallist": "world_silver",
    "World Championships bronze medallist": "world_bronze",
}

STOP_MARKERS = r"Season's bests|SEE MORE|Stay updated"


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
        name = m.group(1).strip().title()
        country = m.group(2).strip()
        events = [e.strip() for e in m.group(3).split(",") if e.strip()]
        return name, country, (events[0] if events else None)

    m = re.match(r"^(.*?),\s*(.*)$", desc)
    if m:
        return m.group(1).strip().title(), m.group(2).strip(), None

    return None, None, None


def parse_birth_date(flat):
    m = re.search(r"Born\s*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})", flat)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%d %b %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_medals(flat):
    medals = {bucket: 0 for bucket in set(TITLE_TO_BUCKET.values())}
    labels_by_length = sorted(TITLE_TO_BUCKET, key=len, reverse=True)
    alternation = "|".join(re.escape(label) for label in labels_by_length)
    for m in re.finditer(rf"(\d+)X\s*({alternation})", flat):
        bucket = TITLE_TO_BUCKET[m.group(2)]
        medals[bucket] = max(medals[bucket], int(m.group(1)))
    return medals


def parse_personal_bests(flat):
    """Find each Result/Date/Score anchor triple and take the event
    name from whatever text sits between the end of the previous
    entry and the start of this one."""
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

    name, country, primary_event = parse_name_and_country(soup)
    if not name:
        raise ValueError(f"Could not find a name/country on {url} — page layout may have changed.")

    pbs = parse_personal_bests(flat)
    if not primary_event and pbs:
        # Meta description didn't give us an event list (seen on some
        # retired athletes' profiles) — fall back to their top personal best.
        primary_event = max(pbs, key=lambda p: p["score"])["event"]

    return {
        "id": slugify(name),
        "name": name,
        "country": country,
        "birth_date": parse_birth_date(flat),
        "primary_event": primary_event,
        "medals": parse_medals(flat),
        "status": guess_status(pbs),
        "personal_bests": pbs,
        "profile_url": url,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--urls", required=True, help="Text file with one worldathletics.org profile URL per line")
    ap.add_argument("--out", required=True, help="Path to write the resulting JSON file")
    ap.add_argument("--delay", type=float, default=3.0, help="Seconds to wait between requests (default 3)")
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
            athletes.append(profile)
        except Exception as exc:
            print(f"  skipped: {exc}", file=sys.stderr)
        if i < len(urls):
            time.sleep(args.delay)

    out = {
        "source_note": "Scraped from worldathletics.org athlete profiles. 'status' is a rough active/retired guess based on how recent the most recent personal best is — check it by hand.",
        "athletes": athletes,
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(athletes)} athletes to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
