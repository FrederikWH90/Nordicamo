// Page wiring: read the form, count, lay out, render and export.
// Nothing is sent anywhere; all processing happens in this browser tab.

import { LIMITS, clip, countWords, fontScale, orderTags, summarize, tokenize } from "./core.js";
import { STOPWORD_LANGUAGES, stopwordSet } from "./stopwords.js";
import { estimateWidth, tagCloudLayout, wordCloudLayout } from "./layout.js";
import { CLOUD_FONT, binaryStringToBytes, composeDocument, toDelimited, toJSON, toPDF, toSVG } from "./export.js";
import { EXAMPLE_TEXT } from "./example.js";

const $ = (id) => document.getElementById(id);
const els = {
  form: $("form"), text: $("text"), charcount: $("charcount"), example: $("example"), clear: $("clear"),
  minChars: $("minChars"), minFreq: $("minFreq"), stopLang: $("stopLang"), maxWords: $("maxWords"),
  method: $("method"), query: $("query"), title: $("title"), credit: $("credit"),
  results: $("results"), summary: $("summary"), note: $("note"), view: $("view"),
  outputBtn: $("outputBtn"), outputMenu: $("outputMenu"),
};
const radio = (name) => document.querySelector(`input[name="${name}"]:checked`).value;

// Blue shades from the Nordicamo palette, darkest for the most frequent words.
const PALETTES = {
  blue: ["#0d366b", "#1c5cab", "#256abf", "#3987e5"],
  black: ["#111111"],
};
const CLOUD_WIDTH = 900;
const WORD_CLOUD_HEIGHT = 560;

let state = { view: "tag", tags: [], last: null };

// Real font metrics for layout, so SVG/PDF/PNG match what is measured.
const canvas = document.createElement("canvas").getContext("2d");
function measure(word, size) {
  if (!canvas) return estimateWidth(word, size);
  canvas.font = `${size}px ${CLOUD_FONT}`;
  return canvas.measureText(word).width;
}

for (const [value, label] of Object.entries(STOPWORD_LANGUAGES)) {
  els.stopLang.add(new Option(label, value));
}

function readOptions() {
  const int = (el, min, fallback) => {
    const n = Number.parseInt(el.value, 10);
    return Number.isFinite(n) && n >= min ? n : fallback;
  };
  return {
    minChars: int(els.minChars, 1, 3),
    minFrequency: int(els.minFreq, 1, 3),
    stop: radio("stop"),
    stopLang: els.stopLang.value,
    ordering: radio("order"),
    rotation: radio("rotation"),
    palette: radio("palette"),
    maxWords: int(els.maxWords, 1, 100),
    method: clip(els.method.value, LIMITS.method),
    query: clip(els.query.value, LIMITS.query),
    title: clip(els.title.value, LIMITS.title),
    credit: els.credit.checked,
  };
}

function colorFor(tags, palette) {
  const shades = PALETTES[palette] ?? PALETTES.blue;
  if (shades.length === 1) return () => shades[0];
  // Rank bands of the shown words: top 10% darkest, then 30%, 60%, rest.
  const counts = tags.map((t) => t.count).sort((a, b) => b - a);
  const cut = (q) => counts[Math.min(counts.length - 1, Math.floor(q * counts.length))];
  const bounds = [cut(0.1), cut(0.3), cut(0.6)];
  return (item) => {
    const band = bounds.findIndex((b) => item.count >= b);
    return shades[band === -1 ? shades.length - 1 : band];
  };
}

function creditLine() {
  const date = new Date().toISOString().slice(0, 10);
  return `Made with the Nordicamo Tag Cloud Generator · tagcloud.nordicamo.org · ${date}`;
}

function buildDocument(opts, view = state.view) {
  const { tags } = state;
  const base = { title: opts.title, method: opts.method, query: opts.query, credit: opts.credit ? creditLine() : "" };
  if (view === "word") {
    const top = orderTags(tags, "frequency").slice(0, opts.maxWords);
    const size = fontScale(top, 12, 64);
    const { items, skipped } = wordCloudLayout(top, {
      width: CLOUD_WIDTH, height: WORD_CLOUD_HEIGHT, size, measure, rotation: opts.rotation,
    });
    const doc = composeDocument(items, { ...base, width: CLOUD_WIDTH, cloudHeight: WORD_CLOUD_HEIGHT, color: colorFor(top, opts.palette) });
    return { doc, shown: items.length, skipped: skipped.length, capped: tags.length - top.length };
  }
  const ordered = orderTags(tags, opts.ordering);
  const size = fontScale(ordered, 13, 48);
  const { items, height } = tagCloudLayout(ordered, { width: CLOUD_WIDTH - 56, size, measure });
  const shifted = items.map((i) => ({ ...i, x: i.x + 28 }));
  const doc = composeDocument(shifted, { ...base, width: CLOUD_WIDTH, cloudHeight: height, color: colorFor(ordered, opts.palette) });
  return { doc, shown: items.length, skipped: 0, capped: 0 };
}

function renderTable(tags) {
  const ordered = orderTags(tags, readOptions().ordering);
  const max = Math.max(...ordered.map((t) => t.count));
  const rows = ordered.map((t, i) => {
    const tr = document.createElement("tr");
    const bar = document.createElement("span");
    bar.className = "bar";
    bar.style.width = `${(t.count / max) * 100}%`;
    const cells = [String(i + 1), t.word, String(t.count)];
    cells.forEach((value, c) => {
      const td = document.createElement("td");
      td.textContent = value;
      if (c === 2) { td.className = "num"; td.prepend(bar); }
      tr.append(td);
    });
    return tr;
  });
  const table = document.createElement("table");
  table.className = "freq";
  table.innerHTML = "<thead><tr><th>#</th><th>Word</th><th class='num'>Frequency</th></tr></thead>";
  const tbody = document.createElement("tbody");
  tbody.append(...rows);
  table.append(tbody);
  return table;
}

function run() {
  const text = els.text.value;
  updateCount();
  const opts = readOptions();
  els.stopLang.disabled = opts.stop !== "remove";
  if (!text.trim()) {
    els.results.hidden = true;
    return;
  }
  const stopwords = opts.stop === "remove" ? stopwordSet(opts.stopLang) : null;
  state.tags = countWords(text, { minChars: opts.minChars, minFrequency: opts.minFrequency, stopwords });
  const s = summarize(text, state.tags);
  els.results.hidden = false;
  els.summary.textContent =
    `${s.totalWords.toLocaleString("en")} words in total, ${s.uniqueWords.toLocaleString("en")} different. ` +
    `Showing ${s.shownTags.toLocaleString("en")} words with at least ${opts.minChars} characters that occur at least ` +
    `${opts.minFrequency} ${opts.minFrequency === 1 ? "time" : "times"}` +
    (stopwords ? `, ${STOPWORD_LANGUAGES[opts.stopLang]} stopwords removed.` : ".");

  els.view.replaceChildren();
  els.note.hidden = true;
  if (!state.tags.length) {
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = `No word occurs ${opts.minFrequency} times or more with these settings. Try a lower minimum frequency or fewer minimum characters.`;
    els.view.append(p);
    state.last = null;
    return;
  }
  if (state.view === "table") {
    els.view.append(renderTable(state.tags));
    state.last = null;
    return;
  }
  state.last = buildDocument(opts);
  const notes = [];
  if (state.last.capped) notes.push(`The word cloud shows the ${opts.maxWords} most frequent words; ${state.last.capped} less frequent words are in the table and downloads.`);
  if (state.last.skipped) notes.push(`${state.last.skipped} words did not fit and were left out of the picture.`);
  if (notes.length) { els.note.textContent = notes.join(" "); els.note.hidden = false; }
  const holder = document.createElement("div");
  holder.className = "cloud";
  // Our own SVG markup; every word is XML-escaped in toSVG.
  holder.innerHTML = toSVG(state.last.doc).replace(/^<\?xml[^>]*>\s*/, "");
  els.view.append(holder);
}

// --- downloads ---------------------------------------------------------------

function fileStem(kind) {
  const title = readOptions().title || "tagcloud";
  const slug = title.toLowerCase().normalize("NFKD").replace(/[^\w]+/g, "-").replace(/^-|-$/g, "") || "tagcloud";
  const suffix = ["csv", "tsv", "json"].includes(kind) ? "frequencies" : state.view === "word" ? "wordcloud" : "tagcloud";
  return `${slug}-${suffix}`;
}

function download(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function exportAs(kind) {
  if (!state.tags.length) return;
  const opts = readOptions();
  const ordered = orderTags(state.tags, opts.ordering);
  const meta = { title: opts.title || undefined, method: opts.method || undefined, query: opts.query || undefined,
                 generated: new Date().toISOString(), tool: "Nordicamo Tag Cloud Generator" };
  if (kind === "csv") return download(new Blob([toDelimited(ordered, ",")], { type: "text/csv;charset=utf-8" }), `${fileStem(kind)}.csv`);
  if (kind === "tsv") return download(new Blob([toDelimited(ordered, "\t")], { type: "text/tab-separated-values;charset=utf-8" }), `${fileStem(kind)}.tsv`);
  if (kind === "json") return download(new Blob([toJSON(ordered, meta)], { type: "application/json" }), `${fileStem(kind)}.json`);

  // Image formats export the selected cloud; from the table view, the tag cloud.
  const { doc } = buildDocument(opts, state.view === "word" ? "word" : "tag");
  const svg = toSVG(doc);
  if (kind === "svg") return download(new Blob([svg], { type: "image/svg+xml" }), `${fileStem(kind)}.svg`);
  if (kind === "pdf") return download(new Blob([binaryStringToBytes(toPDF(doc, measure))], { type: "application/pdf" }), `${fileStem(kind)}.pdf`);
  if (kind === "png") {
    const img = new Image();
    const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
    await new Promise((resolve, reject) => { img.onload = resolve; img.onerror = reject; img.src = url; });
    const scale = 2;
    const c = document.createElement("canvas");
    c.width = doc.width * scale;
    c.height = doc.height * scale;
    const ctx = c.getContext("2d");
    ctx.scale(scale, scale);
    ctx.drawImage(img, 0, 0);
    URL.revokeObjectURL(url);
    c.toBlob((blob) => download(blob, `${fileStem(kind)}.png`), "image/png");
  }
}

// --- events --------------------------------------------------------------------

function updateCount() {
  const n = tokenize(els.text.value).length;
  els.charcount.textContent = `${n.toLocaleString("en")} ${n === 1 ? "word" : "words"}`;
}

let timer;
const rerunSoon = () => {
  if (els.results.hidden) return;
  clearTimeout(timer);
  timer = setTimeout(run, 150);
};

els.form.addEventListener("submit", (e) => { e.preventDefault(); run(); els.results.scrollIntoView({ behavior: "smooth" }); });
els.text.addEventListener("input", updateCount);
els.text.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); els.form.requestSubmit(); }
});
els.form.addEventListener("change", (e) => { if (e.target !== els.text) rerunSoon(); else updateCount(); });
els.form.addEventListener("input", (e) => { if (e.target !== els.text) rerunSoon(); });
els.example.addEventListener("click", () => { els.text.value = EXAMPLE_TEXT; updateCount(); els.form.requestSubmit(); });
els.clear.addEventListener("click", () => { els.text.value = ""; updateCount(); els.results.hidden = true; els.text.focus(); });

document.querySelectorAll('[role="tab"]').forEach((tab) => {
  tab.addEventListener("click", () => {
    state.view = tab.dataset.view;
    document.querySelectorAll('[role="tab"]').forEach((t) => t.setAttribute("aria-selected", String(t === tab)));
    run();
  });
});

const closeMenu = () => { els.outputMenu.hidden = true; els.outputBtn.setAttribute("aria-expanded", "false"); };
els.outputBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  const open = els.outputMenu.hidden;
  els.outputMenu.hidden = !open;
  els.outputBtn.setAttribute("aria-expanded", String(open));
});
els.outputMenu.addEventListener("click", (e) => {
  const kind = e.target.closest("[data-out]")?.dataset.out;
  if (kind) { closeMenu(); exportAs(kind); }
});
document.addEventListener("click", closeMenu);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeMenu(); });

updateCount();
