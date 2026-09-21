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

# World Athletics profile pages list championship titles as lines like
# "3X" followed by a label line such as "World champion". This maps
# the labels we care about to buckets in the output schema.
TITLE_TO_BUCKET = {
    "Olympic champion": "olympic_gold",
    "Olympic Games silver medallist": "olympic_silver",
    "Olympic Games bronze medallist": "olympic_bronze",
    "World champion": "world_gold",
    "World Championships silver medallist": "world_silver",
    "World Championships bronze medallist": "world_bronze",
}

STOP_MARKERS = ("Season", "SEE MORE", "*", "Stay updated")


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def fetch(url, timeout=20):
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_name_and_country(soup):
    meta = soup.find("meta", attrs={"name": "description"})
    desc = meta["content"] if meta and meta.get("content") else ""
    # WA formats this consistently as "NAME, Country - Event, Event, ..."
    m = re.match(r"^(.*?),\s*(.*?)\s*-\s*(.*)$", desc)
    if not m:
        return None, None, None
    name = m.group(1).strip().title()
    country = m.group(2).strip()
    events = [e.strip() for e in m.group(3).split(",") if e.strip()]
    primary_event = events[0] if events else None
    return name, country, primary_event


def parse_birth_date(text):
    m = re.search(r"Born(\d{1,2} [A-Z]{3} \d{4})", text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%d %b %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_medals(lines):
    medals = {b: 0 for b in set(TITLE_TO_BUCKET.values())}
    for i, line in enumerate(lines):
        m = re.match(r"^(\d+)X$", line)
        if m and i + 1 < len(lines):
            bucket = TITLE_TO_BUCKET.get(lines[i + 1])
            if bucket:
                medals[bucket] = int(m.group(1))
    return medals


def parse_personal_bests(lines):
    pbs = []
    try:
        i = lines.index("Personal bests") + 1
    except ValueError:
        return pbs

    n = len(lines)
    while i < n:
        if lines[i].startswith(STOP_MARKERS):
            break
        if i + 1 >= n or lines[i + 1] != "Result":
            break

        event = lines[i]
        result_line = lines[i + 2] if i + 2 < n else ""
        rm = re.match(r"^([\d:.]+)\s*(.*)$", result_line)
        result, record = (rm.group(1), rm.group(2).strip()) if rm else (result_line, "")

        # Scan ahead a few lines for the "Date" and "Score" labels rather
        # than assuming a fixed offset, since some entries carry extra
        # annotations (e.g. "* Not legal").
        date_val, score_val = None, None
        j = i + 3
        limit = min(n, i + 9)
        while j < limit:
            if lines[j] == "Date" and j + 1 < n:
                date_val = lines[j + 1]
            if lines[j] == "Score" and j + 1 < n:
                score_val = lines[j + 1]
                j += 2
                break
            j += 1

        try:
            score_num = int(score_val) if score_val else None
        except ValueError:
            score_num = None

        date_iso = None
        if date_val:
            try:
                date_iso = datetime.strptime(date_val, "%d %b %Y").strftime("%Y-%m-%d")
            except ValueError:
                date_iso = None

        if score_num is not None:
            pbs.append({
                "event": event,
                "result": result,
                "record": record,
                "score": score_num,
                "date": date_iso,
            })

        i = j if j > i else i + 1

    return pbs


def guess_status(pbs):
    if not pbs:
        return "unknown"
    years = [int(pb["date"][:4]) for pb in pbs if pb.get("date")]
    if not years:
        return "unknown"
    return "active" if (datetime.now().year - max(years)) <= 2 else "retired"


def parse_profile(html, url):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    name, country, primary_event = parse_name_and_country(soup)
    if not name:
        raise ValueError(f"Could not find a name/country on {url} — page layout may have changed.")

    return {
        "id": slugify(name),
        "name": name,
        "country": country,
        "birth_date": parse_birth_date(text),
        "primary_event": primary_event,
        "medals": parse_medals(lines),
        "status": guess_status(parse_personal_bests(lines)),
        "personal_bests": parse_personal_bests(lines),
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
            athletes.append(parse_profile(html, url))
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
