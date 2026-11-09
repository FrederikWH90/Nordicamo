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

export function countWords(text, { minChars = 3, minFrequency = 3, stopwords = null } = {}) {
  const counts = new Map();
  for (const word of tokenize(text)) {
    if ([...word].length < minChars) continue;
    if (stopwords && stopwords.has(word)) continue;
    counts.set(word, (counts.get(word) ?? 0) + 1);
  }
  const firstSeen = new Map([...counts.keys()].map((w, i) => [w, i]));
  return [...counts]
    .filter(([, n]) => n >= minFrequency)
    .map(([word, count]) => ({ word, count, order: firstSeen.get(word) }));
}

// "frequency": most frequent first (ties alphabetical); "term": A–Z;
// "unordered": first appearance in the text, like reading order.
export function orderTags(tags, ordering = "frequency") {
  const copy = [...tags];
  const byTerm = (a, b) => a.word.localeCompare(b.word);
  if (ordering === "term") return copy.sort(byTerm);
  if (ordering === "unordered") return copy.sort((a, b) => a.order - b.order);
  return copy.sort((a, b) => b.count - a.count || byTerm(a, b));
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
