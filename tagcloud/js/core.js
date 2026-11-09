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

function countSequence(items) {
  const counts = new Map();
  const order = new Map();
  items.forEach((unit, i) => {
    if (!counts.has(unit)) order.set(unit, i);
    counts.set(unit, (counts.get(unit) ?? 0) + 1);
  });
  return { counts, order };
}

function phrases(kept, n) {
  const out = [];
  for (let i = 0; i <= kept.length - n; i++) out.push(kept.slice(i, i + n).join(" "));
  return out;
}

// A phrase is certain when it accounts for most of the rarer word's occurrences:
// "york" almost only inside "new york", not every pair that happens to sit together.
export const PHRASE_CERTAINTY = 0.6;

function isCertain(phrase, phraseCount, wordCounts) {
  const weakest = Math.min(...phrase.split(" ").map((part) => wordCounts.get(part) || 0));
  return weakest > 0 && phraseCount / weakest >= PHRASE_CERTAINTY;
}

function tally(text, { minChars = 3, minFrequency = 3, stopwords = null } = {}) {
  const { tokens, kept } = contentTokens(text, { minChars, stopwords });
  const words = countSequence(kept);
  const bigrams = countSequence(phrases(kept, 2));
  const trigrams = countSequence(phrases(kept, 3));
  const certain = (bag) => [...bag.counts].filter(([phrase, n]) => n >= minFrequency && isCertain(phrase, n, words.counts));
  const keptTrigrams = certain(trigrams);
  const trigramCounts = new Map(keptTrigrams);
  const keptBigrams = certain(bigrams).filter(([phrase, n]) => {
    for (const [tri, triCount] of trigramCounts) {
      if (tri.includes(phrase) && triCount >= n * 0.8) return false;
    }
    return true;
  });
  const counts = new Map(words.counts);
  const order = new Map(words.order);
  for (const [phrase, n] of [...keptBigrams, ...keptTrigrams]) {
    counts.set(phrase, n);
    order.set(phrase, (phrase.split(" ").length === 2 ? bigrams : trigrams).order.get(phrase));
  }
  return { counts, order, total: tokens.length };
}

export function countWords(text, { minChars = 3, minFrequency = 3, stopwords = null } = {}) {
  const { counts, order } = tally(text, { minChars, minFrequency, stopwords });
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
export function compareWords(textA, textB, { minChars = 3, minFrequency = 3, stopwords = null } = {}) {
  const left = tally(textA, { minChars, minFrequency, stopwords });
  const right = tally(textB, { minChars, minFrequency, stopwords });
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
