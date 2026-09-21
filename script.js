// Statlete — guess the mystery track and field athlete.
// Loads data/athletes.json, derives a few fields client-side (continent,
// event group, display units), and runs a small Wordle-style guessing game.

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
    pbs: raw.personal_bests.map(p => ({ event: p.event, display: formatDisplay(p), score: p.score }))
  };
}

let athletes = [];
let masterEvents = [];
let target = null;
let guessedNames = new Set();
let revealed = {};

const els = {
  board: document.getElementById("board"),
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

function numCell(td, gVal, tVal) {
  td.textContent = gVal;
  if (gVal === tVal) {
    td.classList.add("match");
  } else {
    td.appendChild(arrow(tVal > gVal ? "up" : "down"));
  }
}

function renderGuessRow(g) {
  const tr = document.createElement("tr");

  const nameTd = document.createElement("td");
  nameTd.className = "col-name";
  nameTd.textContent = g.name;
  tr.appendChild(nameTd);

  const countryTd = document.createElement("td");
  countryTd.textContent = g.country;
  if (g.country === target.country) countryTd.classList.add("match");
  else if (g.continent === target.continent) countryTd.classList.add("partial");
  tr.appendChild(countryTd);

  const bornTd = document.createElement("td");
  numCell(bornTd, g.born, target.born);
  tr.appendChild(bornTd);

  const medalsTd = document.createElement("td");
  numCell(medalsTd, g.medals, target.medals);
  tr.appendChild(medalsTd);

  const scoreTd = document.createElement("td");
  numCell(scoreTd, g.score, target.score);
  tr.appendChild(scoreTd);

  const statusTd = document.createElement("td");
  statusTd.textContent = g.status;
  if (g.status === target.status) statusTd.classList.add("match");
  tr.appendChild(statusTd);

  els.guesses.prepend(tr);
}

function updateBoard(g) {
  g.pbs.forEach(pb => {
    const targetPb = target.pbs.find(p => p.event === pb.event);
    let state, dir = null;
    if (g.name === target.name || (targetPb && targetPb.score === pb.score)) {
      state = "match";
    } else if (targetPb) {
      state = "cmp";
      dir = targetPb.score > pb.score ? "up" : "down";
    } else {
      state = groupFromEvent(pb.event) === target.group ? "partial" : "plain";
    }
    revealed[pb.event] = { display: pb.display, state, dir };
  });
  renderBoard();
}

function renderBoard() {
  const keys = masterEvents.filter(e => revealed[e]);
  if (keys.length === 0) {
    els.board.innerHTML = '<p class="empty">Guess an athlete to start revealing the events they hold a personal best in.</p>';
    return;
  }
  els.board.innerHTML = "";
  keys.forEach(e => {
    const r = revealed[e];
    const row = document.createElement("div");
    row.className = "ev-row" + (r.state === "match" ? " match" : r.state === "partial" ? " partial" : "");
    const name = document.createElement("span");
    name.className = "ev-name";
    name.textContent = e;
    const val = document.createElement("span");
    val.className = "ev-val";
    val.textContent = r.display;
    if (r.dir) val.appendChild(arrow(r.dir));
    row.appendChild(name);
    row.appendChild(val);
    els.board.appendChild(row);
  });
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
  renderGuessRow(found);
  updateBoard(found);
  els.input.value = "";
  if (found.name === target.name) endGame(true);
  else if (guessedNames.size >= athletes.length) endGame(false);
}

function newGame() {
  pickTarget();
  guessedNames = new Set();
  revealed = {};
  els.guesses.innerHTML = "";
  els.status.textContent = "";
  els.error.hidden = true;
  els.reset.hidden = true;
  els.input.disabled = false;
  els.form.querySelector("button").disabled = false;
  els.input.value = "";
  renderBoard();
}

async function init() {
  const res = await fetch("data/athletes.json");
  const data = await res.json();
  athletes = data.athletes.map(buildAthlete);
  const seen = new Set();
  masterEvents = [];
  data.athletes.forEach(a => a.personal_bests.forEach(pb => {
    if (!seen.has(pb.event)) { seen.add(pb.event); masterEvents.push(pb.event); }
  }));
  els.list.innerHTML = athletes.map(a => `<option value="${a.name}">`).join("");
  els.form.addEventListener("submit", submitGuess);
  els.reset.addEventListener("click", newGame);
  newGame();
}

init();
