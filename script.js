// Statlete — guess the mystery track and field athlete.
// Loads data/athletes.json, derives a few fields client-side (continent,
// event group, display units), and runs a small guessing game where each
// guess renders as its own card (Spotle-style) rather than one shared table.

const CONTINENTS = {
  "Norway": "Europe", "Sweden": "Europe", "Netherlands": "Europe", "Great Britain": "Europe",
  "United Kingdom": "Europe", "Germany": "Europe", "France": "Europe", "Italy": "Europe",
  "Spain": "Europe", "Poland": "Europe", "Belgium": "Europe", "Portugal": "Europe",
  "Switzerland": "Europe", "Ireland": "Europe", "Czechia": "Europe", "Greece": "Europe",
  "United States": "North America", "Jamaica": "North America", "Canada": "North America",
  "Bahamas": "North America", "Dominican Republic": "North America", "Cuba": "North America",
  "Kenya": "Africa", "Ethiopia": "Africa", "Nigeria": "Africa", "South Africa": "Africa",
  "Botswana": "Africa", "Uganda": "Africa", "Morocco": "Africa", "Algeria": "Africa",
  "Australia": "Oceania", "New Zealand": "Oceania",
  "China": "Asia", "Japan": "Asia", "Qatar": "Asia", "India": "Asia",
  "Brazil": "South America", "Colombia": "South America", "Venezuela": "South America"
};

const PBS_SHOWN_BY_DEFAULT = 6;

function continentOf(country) {
  return CONTINENTS[country] || "Other";
}

function groupFromEvent(eventName) {
  const e = eventName.toLowerCase();
  if (e.includes("hurdles")) return "Hurdles";
  if (e.includes("vault") || e.includes("jump")) return "Jumps";
  if (e.includes("put") || e.includes("discus") || e.includes("javelin") || e.includes("hammer")) return "Throws";
  if (e.includes("decathlon") || e.includes("heptathlon")) return "Multi-events";
  if (e.includes("relay")) return "Sprints";
  if (e.includes("mile")) return "Middle/long distance";
  const m = e.match(/(\d+)\s*metres/);
  if (m) return parseInt(m[1], 10) <= 400 ? "Sprints" : "Middle/long distance";
  return "Other";
}

function formatDisplay(pb) {
  if (pb.result.includes(":")) return pb.result;
  const group = groupFromEvent(pb.event);
  if (group === "Multi-events") return pb.result + " pts";
  if (group === "Jumps" || group === "Throws") return pb.result + "m";
  return pb.result + "s";
}

function totalMedals(m) {
  return m.olympic_gold + m.olympic_silver + m.olympic_bronze
       + m.world_gold + m.world_silver + m.world_bronze;
}

function topScore(pbs) {
  return Math.max(...pbs.map(p => p.score));
}

function buildAthlete(raw) {
  return {
    name: raw.name,
    country: raw.country,
    continent: continentOf(raw.country),
    born: parseInt(raw.birth_date.slice(0, 4), 10),
    group: groupFromEvent(raw.primary_event),
    medals: totalMedals(raw.medals),
    score: topScore(raw.personal_bests),
    status: raw.status === "retired" ? "Retired" : "Active",
    // Sorted best-first so "show more" reveals the most impressive marks first.
    pbs: raw.personal_bests
      .map(p => ({ event: p.event, display: formatDisplay(p), score: p.score }))
      .sort((a, b) => b.score - a.score)
  };
}

let athletes = [];
let target = null;
let guessedNames = new Set();

const els = {
  guesses: document.getElementById("guesses"),
  form: document.getElementById("guess-form"),
  input: document.getElementById("guess-input"),
  list: document.getElementById("athlete-list"),
  error: document.getElementById("error"),
  status: document.getElementById("status"),
  reset: document.getElementById("reset"),
};

function pickTarget() {
  const pool = athletes.filter(a => !target || a.name !== target.name);
  target = pool[Math.floor(Math.random() * pool.length)];
}

function arrow(dir) {
  const span = document.createElement("span");
  span.className = "arrow";
  span.setAttribute("aria-hidden", "true");
  span.textContent = dir === "up" ? "\u2191" : "\u2193";
  return span;
}

function chip(labelText, valueText, state) {
  const span = document.createElement("span");
  span.className = "chip" + (state ? " " + state : "");
  const label = document.createElement("span");
  label.className = "chip-label";
  label.textContent = labelText;
  span.appendChild(label);
  span.appendChild(document.createTextNode(valueText));
  return span;
}

function numChip(labelText, gVal, tVal) {
  if (gVal === tVal) return chip(labelText, String(gVal), "match");
  const c = chip(labelText, String(gVal), null);
  c.appendChild(arrow(tVal > gVal ? "up" : "down"));
  return c;
}

function countryChip(g) {
  if (g.country === target.country) return chip("Country", g.country, "match");
  if (g.continent === target.continent) return chip("Country", g.country, "partial");
  return chip("Country", g.country, null);
}

function statusChip(g) {
  return chip("Status", g.status, g.status === target.status ? "match" : null);
}

function pbState(pb) {
  const targetPb = target.pbs.find(p => p.event === pb.event);
  if (targetPb && targetPb.score === pb.score) return { state: "match", dir: null };
  if (targetPb) return { state: "cmp", dir: targetPb.score > pb.score ? "up" : "down" };
  return { state: groupFromEvent(pb.event) === target.group ? "partial" : "plain", dir: null };
}

function pbRow(pb) {
  const { state, dir } = pbState(pb);
  const row = document.createElement("div");
  row.className = "ev-row" + (state === "match" ? " match" : state === "partial" ? " partial" : "");
  const name = document.createElement("span");
  name.className = "ev-name";
  name.textContent = pb.event;
  const val = document.createElement("span");
  val.className = "ev-val";
  val.textContent = pb.display;
  if (dir) val.appendChild(arrow(dir));
  row.appendChild(name);
  row.appendChild(val);
  return row;
}

function renderGuessCard(g) {
  const placeholder = els.guesses.querySelector(".empty");
  if (placeholder) placeholder.remove();

  const card = document.createElement("div");
  card.className = "guess-card";

  const name = document.createElement("span");
  name.className = "gc-name";
  name.textContent = g.name;
  card.appendChild(name);

  const chips = document.createElement("div");
  chips.className = "gc-chips";
  chips.appendChild(countryChip(g));
  chips.appendChild(numChip("Born", g.born, target.born));
  chips.appendChild(numChip("Medals", g.medals, target.medals));
  chips.appendChild(numChip("Score", g.score, target.score));
  chips.appendChild(statusChip(g));
  card.appendChild(chips);

  const pbsHeading = document.createElement("p");
  pbsHeading.className = "gc-pbs-heading";
  pbsHeading.textContent = `Personal bests (${g.pbs.length})`;
  card.appendChild(pbsHeading);

  const pbsWrap = document.createElement("div");
  g.pbs.slice(0, PBS_SHOWN_BY_DEFAULT).forEach(pb => pbsWrap.appendChild(pbRow(pb)));
  card.appendChild(pbsWrap);

  if (g.pbs.length > PBS_SHOWN_BY_DEFAULT) {
    const remaining = g.pbs.slice(PBS_SHOWN_BY_DEFAULT);
    const moreBtn = document.createElement("button");
    moreBtn.type = "button";
    moreBtn.className = "show-more";
    moreBtn.textContent = `Show ${remaining.length} more`;
    moreBtn.addEventListener("click", () => {
      remaining.forEach(pb => pbsWrap.appendChild(pbRow(pb)));
      moreBtn.remove();
    });
    card.appendChild(moreBtn);
  }

  els.guesses.prepend(card);
}

function endGame(won) {
  els.status.textContent = won
    ? `Correct — it was ${target.name}.`
    : `Out of athletes — it was ${target.name}.`;
  els.input.disabled = true;
  els.form.querySelector("button").disabled = true;
  els.reset.hidden = false;
}

function submitGuess(ev) {
  ev.preventDefault();
  els.error.hidden = true;
  const val = els.input.value.trim();
  if (!val) {
    els.error.textContent = "Enter an athlete name first.";
    els.error.hidden = false;
    return;
  }
  const found = athletes.find(a => a.name.toLowerCase() === val.toLowerCase());
  if (!found) {
    els.error.textContent = "Pick a name from the list.";
    els.error.hidden = false;
    return;
  }
  if (guessedNames.has(found.name)) {
    els.error.textContent = "Already guessed that one.";
    els.error.hidden = false;
    return;
  }
  guessedNames.add(found.name);
  renderGuessCard(found);
  els.input.value = "";
  if (found.name === target.name) endGame(true);
  else if (guessedNames.size >= athletes.length) endGame(false);
}

function newGame() {
  pickTarget();
  guessedNames = new Set();
  els.guesses.innerHTML = '<p class="empty">Make a guess to see how close you are.</p>';
  els.status.textContent = "";
  els.error.hidden = true;
  els.reset.hidden = true;
  els.input.disabled = false;
  els.form.querySelector("button").disabled = false;
  els.input.value = "";
}

async function init() {
  const res = await fetch("data/athletes.json");
  const data = await res.json();
  athletes = data.athletes.map(buildAthlete);
  els.list.innerHTML = athletes.map(a => `<option value="${a.name}">`).join("");
  els.form.addEventListener("submit", submitGuess);
  els.reset.addEventListener("click", newGame);
  newGame();
}

init();
