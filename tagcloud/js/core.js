// Counting and shaping words for the tag cloud. Pure functions, no DOM:
// the same code runs in the browser and in the Node tests.

// A word is a run of letters/digits; apostrophes and hyphens are kept
// inside a word ("don't", "low-quality") but never at its edges.
const WORD = /[\p{L}\p{N}]+(?:['’‐‑-][\p{L}\p{N}]+)*/gu;

export function tokenize(text) {
  return (String(text ?? "").normalize("NFC").match(WORD) ?? []).map((w) =>
    w.toLocaleLowerCase().replace(/[’]/g, "'").replace(/[‐‑]/g, "-"),
  );
}

function contentTokens(text, { minChars = 3, stopwords = null } = {}) {
  const tokens = tokenize(text);
  const kept = [];
  for (const word of tokens) {
    if ([...word].length < minChars) continue;
    if (stopwords && stopwords.has(word)) continue;
    kept.push(word);
  }
  return { tokens, kept };
}

function termUnits(kept, terms) {
  const phrases = (n) => {
    const out = [];
    for (let i = 0; i <= kept.length - n; i++) out.push(kept.slice(i, i + n).join(" "));
    return out;
  };
  if (terms === "bigrams") return phrases(2);
  if (terms === "trigrams") return phrases(3);
  if (terms === "all") return [...kept, ...phrases(2), ...phrases(3)];
  return kept;
}

function tally(text, { minChars = 3, stopwords = null, terms = "words" } = {}) {
  const { tokens, kept } = contentTokens(text, { minChars, stopwords });
  const counts = new Map();
  const order = new Map();
  termUnits(kept, terms).forEach((unit, i) => {
    if (!counts.has(unit)) order.set(unit, i);
    counts.set(unit, (counts.get(unit) ?? 0) + 1);
  });
  return { counts, order, total: tokens.length };
}

export function countWords(text, { minChars = 3, minFrequency = 3, stopwords = null, terms = "words" } = {}) {
  const { counts, order } = tally(text, { minChars, stopwords, terms });
  return [...counts]
    .filter(([, n]) => n >= minFrequency)
    .map(([word, count]) => ({ word, count, order: order.get(word) }));
}

// "frequency": most frequent first (ties alphabetical); "term": A–Z;
// "unordered": first appearance in the text, like reading order;
// "balance": text A, then shared, then text B (comparison mode).
export function orderTags(tags, ordering = "frequency") {
  const copy = [...tags];
  const byTerm = (a, b) => a.word.localeCompare(b.word);
  if (ordering === "term") return copy.sort(byTerm);
  if (ordering === "unordered") return copy.sort((a, b) => a.order - b.order);
  if (ordering === "balance") return copy.sort((a, b) => (b.lean ?? 0) - (a.lean ?? 0) || byTerm(a, b));
  return copy.sort((a, b) => b.count - a.count || byTerm(a, b));
}

// Blue and orange, readable on white, and distinct for red-green colour blindness.
// Strong colour: one text uses the word at least three times as often, per word.
// Lighter colour: a milder lean. Grey: the two texts use it about equally.
export const COMPARE_COLORS = {
  a: "#0C4A8A",
  "a-more": "#3E7CB8",
  shared: "#5C6770",
  "b-more": "#C47E2A",
  b: "#C25100",
};

export function leanSide(lean) {
  if (lean >= 0.5) return "a";
  if (lean > 0.12) return "a-more";
  if (lean <= -0.5) return "b";
  if (lean < -0.12) return "b-more";
  return "shared";
}

/**
 * Words from two texts in one list.
 * `count` is the combined frequency (this sets the font size).
 * `lean` is which text uses the word more, as a share of that text's length,
 * from 1 (only the first text) to -1 (only the second). A long text therefore
 * does not drown a short one just by having more raw mentions.
 */
export function compareWords(textA, textB, { minChars = 3, minFrequency = 3, stopwords = null, terms = "words" } = {}) {
  const left = tally(textA, { minChars, stopwords, terms });
  const right = tally(textB, { minChars, stopwords, terms });
  const tags = [];
  for (const word of new Set([...left.counts.keys(), ...right.counts.keys()])) {
    const countA = left.counts.get(word) ?? 0;
    const countB = right.counts.get(word) ?? 0;
    const count = countA + countB;
    if (count < minFrequency) continue;
    const rateA = countA / Math.max(left.total, 1);
    const rateB = countB / Math.max(right.total, 1);
    const lean = rateA + rateB === 0 ? 0 : (rateA - rateB) / (rateA + rateB);
    const order = left.order.has(word) ? left.order.get(word) : left.total + (right.order.get(word) ?? 0);
    tags.push({ word, count, countA, countB, rateA, rateB, lean, side: leanSide(lean), order });
  }
  return { tags, lengthA: left.total, lengthB: right.total };
}

// Font size grows with the square root of the count, so one very frequent
// word doesn't shrink everything else to the minimum size.
export function fontScale(tags, minSize = 13, maxSize = 54) {
  const counts = tags.map((t) => t.count);
  const lo = Math.sqrt(Math.min(...counts));
  const hi = Math.sqrt(Math.max(...counts));
  return (count) => (hi === lo ? (minSize + maxSize) / 2 : minSize + ((Math.sqrt(count) - lo) / (hi - lo)) * (maxSize - minSize));
}

export function summarize(text, tags) {
  const tokens = tokenize(text);
  return {
    totalWords: tokens.length,
    uniqueWords: new Set(tokens).size,
    shownTags: tags.length,
    shownOccurrences: tags.reduce((sum, t) => sum + t.count, 0),
  };
}

export const LIMITS = { method: 55, query: 55, title: 45 };

export function clip(value, max) {
  return [...String(value ?? "").trim()].slice(0, max).join("");
}
