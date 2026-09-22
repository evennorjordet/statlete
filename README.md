# Statlete

A guessing game for track and field athletes: work out the mystery
athlete from clues about country/continent, birth year, career
medals, points score, and active/retired status. Each guess renders
as its own card with its full personal-bests list, stacking newest
on top — rather than merging every guess into one shared table.

- **The site** (`index.html`, `style.css`, `script.js`, `data/`) is a
  static page — no build step, no backend. See below for hosting it
  on GitHub Pages.
- **The scraper** (`scraper/`) pulls fresh athlete data from
  worldathletics.org profile pages and writes `data/athletes.json`.
  See `scraper/README.md` for how it works and its limitations.
- **`.github/workflows/update-data.yml`** runs the scraper on GitHub
  itself — manually on demand, or automatically every Monday — and
  commits the refreshed data straight into the repo.

## 1. Push this to GitHub

From inside this folder:

```
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

(Create the empty repo on GitHub first — github.com → New repository
— then use the URL it gives you in the `remote add` line above.)

## 2. Turn on GitHub Pages

1. In your repo on GitHub, go to **Settings → Pages**.
2. Under "Build and deployment", set Source to **Deploy from a
   branch**.
3. Pick branch **main**, folder **/ (root)**, then Save.
4. GitHub builds it and gives you a URL like
   `https://<your-username>.github.io/<repo-name>/` within a minute
   or two. That's your live, free-hosted game.

Any time you push a change (including an automatic data update, see
below), Pages redeploys automatically — no extra step.

## 3. Run the scraper on GitHub

The workflow file is already in `.github/workflows/update-data.yml`.
Once it's pushed:

1. Go to the **Actions** tab on your repo.
2. You'll see "Update athlete data" listed. Click it, then click
   **Run workflow** to trigger it manually the first time.
3. It checks out the repo, installs the scraper's dependencies, runs
   `scraper/scrape_athletes.py` against the URLs in
   `scraper/athlete_urls.txt`, and if `data/athletes.json` changed,
   commits and pushes that change back to `main` automatically.
4. Pages picks up the new commit and redeploys the site with the
   refreshed data, with nothing else for you to do.

It also runs automatically every Monday morning (see the `schedule`
line in the workflow file — edit the cron expression if you'd rather
it ran less often, since the scraper only refreshes whatever's in
`athlete_urls.txt`, it won't discover new athletes on its own).

To add more athletes: add their profile URLs to
`scraper/athlete_urls.txt`, then either wait for the weekly run or
trigger the workflow manually from the Actions tab.

## Notes

- GitHub Actions runs on GitHub's own servers, not your computer —
  that's what "running the scraping script there" means. Each run
  is a fresh temporary machine that spins up, does the job, and
  disappears.
- The workflow needs no secrets or extra setup — `permissions:
  contents: write` (already in the file) is what lets it push its
  own commit back to the repo.
- Everything here works the same if you'd rather run
  `scraper/scrape_athletes.py` locally rather than through Actions —
  see `scraper/README.md`.
