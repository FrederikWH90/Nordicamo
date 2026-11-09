import { test } from "node:test";
import assert from "node:assert/strict";

import { COMPARE_COLORS, clip, compareWords, countWords, fontScale, leanSide, orderTags, summarize, tokenize } from "../js/core.js";
import { comparisonPlot, estimateWidth, fitToFrame, tagCloudLayout, wordCloudLayout } from "../js/layout.js";
import { composeDocument, plotDocument, toDelimited, toJSON, toPDF, toSVG, winAnsi } from "../js/export.js";
import { DEFAULT_STOPWORD_LANGUAGE, STOPWORD_LANGUAGES, stopwordSet } from "../js/stopwords.js";

const SAMPLE = `Coral Hart has published more than 370 books since February 2025 using artificial intelligence.
"Grifter", "villain" -- insults abound on social media to describe the author. Coral Hart said the AI books
are selling. Hart said AI models have "improved vastly". The prose has improved. The syntax has improved.
Readers don't read rubbish books; they return them, Hart said. Low‑quality AI slop, critics say.`;

test("tokenize keeps inner apostrophes and hyphens, lower-cases, drops punctuation", () => {
  assert.deepEqual(tokenize(`Don't stop -- the low‑quality "AI" isn't Æble's.`), [
    "don't", "stop", "the", "low-quality", "ai", "isn't", "æble's",
  ]);
  assert.deepEqual(tokenize(""), []);
  assert.deepEqual(tokenize(null), []);
});

test("countWords applies minimum characters and minimum frequency", () => {
  const tags = countWords(SAMPLE, { minChars: 3, minFrequency: 3 });
  const map = Object.fromEntries(tags.map((t) => [t.word, t.count]));
  assert.equal(map.hart, 4);
  assert.equal(map.books, 3);
  assert.equal(map.said, 3);
  assert.equal(map.improved, 3);
  assert.equal(map.ai, undefined, "ai has only 2 characters");
  assert.equal(map.coral, undefined, "coral occurs only twice");
});

test("stopword removal", () => {
  const keep = countWords(SAMPLE, { minChars: 3, minFrequency: 2 }).map((t) => t.word);
  const removed = countWords(SAMPLE, { minChars: 3, minFrequency: 2, stopwords: stopwordSet("english") }).map((t) => t.word);
  assert.ok(keep.includes("the") && keep.includes("has"));
  assert.ok(!removed.includes("the") && !removed.includes("has"));
  assert.ok(removed.includes("hart"));
  for (const lang of ["danish", "swedish", "norwegian", "finnish", "german"]) assert.ok(stopwordSet(lang).size > 50, lang);
  assert.ok(stopwordSet("all").has("og") && stopwordSet("all").has("the"));
  assert.ok(stopwordSet("unknown").has("the"), "falls back to English");
  assert.equal(DEFAULT_STOPWORD_LANGUAGE, "danish");
  assert.equal(STOPWORD_LANGUAGES.danish, "Dansk");
  for (const word of ["og", "ikke", "at", "så", "blevet", "fordi"]) {
    assert.ok(stopwordSet("danish").has(word), word);
  }
});

test("ordering by frequency, by term and unordered (reading order)", () => {
  const tags = countWords("beta alpha beta gamma beta alpha", { minChars: 1, minFrequency: 1 });
  assert.deepEqual(orderTags(tags, "frequency").map((t) => t.word), ["beta", "alpha", "gamma"]);
  assert.deepEqual(orderTags(tags, "term").map((t) => t.word), ["alpha", "beta", "gamma"]);
  assert.deepEqual(orderTags(tags, "unordered").map((t) => t.word), ["beta", "alpha", "gamma"]);
});

test("comparison colours follow relative use, not raw length", () => {
  const shortA = "wind ".repeat(3); // 3 tokens, all wind
  const longB = `${"wind ".repeat(3)}${"nuclear ".repeat(90)}`; // same 3 wind mentions, drowned in raw counts
  const { tags, lengthA, lengthB } = compareWords(shortA, longB, { minChars: 3, minFrequency: 1 });
  const byWord = Object.fromEntries(tags.map((t) => [t.word, t]));
  assert.equal(lengthA, 3);
  assert.ok(lengthB > 90);
  assert.equal(byWord.wind.count, 6);
  assert.equal(byWord.wind.side, "a", "the short text is entirely about wind");
  assert.equal(byWord.nuclear.countA, 0);
  assert.equal(byWord.nuclear.side, "b");
  assert.equal(COMPARE_COLORS[byWord.wind.side], "#0C4A8A");
  assert.equal(COMPARE_COLORS.b, "#C25100");
  assert.equal(COMPARE_COLORS.shared, "#5C6770");

  const equal = compareWords("alpha alpha alpha", "alpha alpha alpha", { minChars: 3, minFrequency: 1 });
  assert.equal(equal.tags[0].side, "shared");
  assert.equal(leanSide(0.2), "a-more");
  assert.equal(leanSide(-0.2), "b-more");
});

test("comparison ordering runs from the first text through shared words to the second", () => {
  const { tags } = compareWords("alpha alpha alpha beta", "gamma gamma gamma beta", { minChars: 3, minFrequency: 1 });
  assert.deepEqual(orderTags(tags, "balance").map((t) => t.word), ["alpha", "beta", "gamma"]);
  const beta = tags.find((t) => t.word === "beta");
  assert.equal(beta.countA, 1);
  assert.equal(beta.countB, 1);
  assert.equal(beta.count, 2);
});

test("comparison minimum frequency uses the combined count", () => {
  const { tags } = compareWords("alpha alpha", "alpha", { minChars: 3, minFrequency: 3 });
  assert.deepEqual(tags.map((t) => t.word), ["alpha"]);
  const dropped = compareWords("alpha alpha", "beta", { minChars: 3, minFrequency: 3 });
  assert.equal(dropped.tags.length, 0);
});

test("comparison plot puts equal share on the diagonal and unique words on the axes", () => {
  const tags = [
    { word: "onlya", rateA: 0.2, rateB: 0, count: 4, countA: 4, countB: 0, side: "a" },
    { word: "onlyb", rateA: 0, rateB: 0.2, count: 4, countA: 0, countB: 4, side: "b" },
    { word: "both", rateA: 0.1, rateB: 0.1, count: 4, countA: 2, countB: 2, side: "shared" },
    { word: "peak", rateA: 0.4, rateB: 0.1, count: 8, countA: 6, countB: 2, side: "a" },
  ];
  const plot = comparisonPlot(tags, { width: 500, height: 500, marginLeft: 40, marginRight: 40, marginTop: 40, marginBottom: 40 });
  const at = Object.fromEntries(plot.points.map((p) => [p.word, p]));
  assert.equal(at.onlya.y, plot.origin.y);
  assert.equal(at.onlyb.x, plot.origin.x);
  assert.ok(Math.abs((at.both.x - plot.origin.x) - (plot.origin.y - at.both.y)) < 0.01, "equal share lies on the diagonal");
  assert.equal(at.peak.x, plot.xEnd.x, "the highest share reaches the end of the axis");
  assert.ok(at.peak.y > plot.yEnd.y && at.peak.y < plot.origin.y);
  assert.deepEqual(plot.diagonal, { x1: plot.origin.x, y1: plot.origin.y, x2: plot.xEnd.x, y2: plot.yEnd.y });
  const svg = toSVG(plotDocument(plot, { nameA: "North", nameB: "South", color: () => "#0C4A8A" }));
  assert.ok(svg.includes('stroke-dasharray="2 5"'));
  assert.ok(svg.includes("equal share") && svg.includes("North →") && svg.includes("↑ South"));
  assert.ok(svg.includes("<circle"));
});

test("font scale is monotonic and bounded", () => {
  const tags = [{ count: 3 }, { count: 10 }, { count: 50 }];
  const size = fontScale(tags, 12, 60);
  assert.equal(size(3), 12);
  assert.equal(size(50), 60);
  assert.ok(size(10) > 12 && size(10) < 60);
  assert.equal(fontScale([{ count: 4 }, { count: 4 }], 10, 20)(4), 15);
});

test("summary and input limits", () => {
  const tags = countWords(SAMPLE);
  const s = summarize(SAMPLE, tags);
  assert.ok(s.totalWords > s.uniqueWords);
  assert.equal(s.shownTags, tags.length);
  assert.equal(clip("x".repeat(80), 55).length, 55);
  assert.equal(clip("  Title  ", 45), "Title");
});

test("word cloud layout places words inside the frame without overlaps", () => {
  const tags = Array.from({ length: 60 }, (_, i) => ({ word: `word${i}`, count: 60 - i }));
  const size = fontScale(tags, 12, 48);
  const { items } = wordCloudLayout(tags, { width: 800, height: 500, size, measure: estimateWidth, rotation: "some" });
  assert.ok(items.length >= 50, `placed ${items.length}`);
  for (const a of items) {
    assert.ok(a.x - a.w / 2 >= 0 && a.x + a.w / 2 <= 800 && a.y - a.h / 2 >= 0 && a.y + a.h / 2 <= 500);
  }
  for (let i = 0; i < items.length; i++) {
    for (let j = i + 1; j < items.length; j++) {
      const a = items[i], b = items[j];
      const sep = a.x + a.w / 2 <= b.x - b.w / 2 || b.x + b.w / 2 <= a.x - a.w / 2 ||
                  a.y + a.h / 2 <= b.y - b.h / 2 || b.y + b.h / 2 <= a.y - a.h / 2;
      assert.ok(sep, `${a.word} overlaps ${b.word}`);
    }
  }
  assert.equal(items[0].word, "word0", "most frequent word placed first");
  assert.ok(items.some((i) => i.rotate === -90), "some words are vertical");
  const again = wordCloudLayout(tags, { width: 800, height: 500, size, measure: estimateWidth, rotation: "some" });
  assert.deepEqual(again.items.map((i) => [i.word, i.x]), items.map((i) => [i.word, i.x]), "deterministic");
});

test("tag cloud layout keeps order and wraps lines within the width", () => {
  const tags = orderTags(countWords(SAMPLE, { minFrequency: 1 }), "term");
  const size = fontScale(tags);
  const { items, height } = tagCloudLayout(tags, { width: 400, size, measure: estimateWidth });
  assert.deepEqual(items.map((i) => i.word), tags.map((t) => t.word));
  for (const i of items) assert.ok(i.x - i.w / 2 >= -0.01 && i.x + i.w / 2 <= 400.01, i.word);
  assert.ok(height > 0);
});

test("delimited and JSON exports", () => {
  const tags = [{ word: 'say "hi"', count: 2 }, { word: "plain", count: 1 }];
  assert.equal(toDelimited(tags), 'word,frequency\n"say ""hi""",2\nplain,1\n');
  assert.equal(toDelimited([{ word: "a", count: 1 }], "\t"), "word\tfrequency\na\t1\n");
  const json = JSON.parse(toJSON(tags, { title: "T" }));
  assert.equal(json.title, "T");
  assert.deepEqual(json.tags[0], { word: 'say "hi"', frequency: 2 });
  const compared = [{ word: "wind", count: 6, countA: 3, countB: 3 }];
  assert.equal(toDelimited(compared, ",", { a: "North, Energy", b: "South" }),
    'word,frequency,"North, Energy",South\nwind,6,3,3\n');
  const comparedJson = JSON.parse(toJSON(compared, { text_a: "North Energy" }));
  assert.deepEqual(comparedJson.tags[0], { word: "wind", frequency: 6, text_a: 3, text_b: 3 });
});

test("SVG includes title, method, query and escapes text", () => {
  const items = [{ word: "<b>&", count: 3, x: 100, y: 50, size: 20, rotate: 0 }, { word: "up", count: 2, x: 200, y: 50, size: 14, rotate: -90 }];
  const doc = composeDocument(items, { width: 400, cloudHeight: 100, title: "My cloud", method: "Word frequency", query: "AFP article", credit: "Nordicamo", color: () => "#173f5f" });
  const svg = toSVG(doc);
  assert.ok(svg.startsWith("<?xml"));
  assert.ok(svg.includes(">My cloud<") && svg.includes("Method: Word frequency") && svg.includes("Query: AFP article"));
  assert.ok(svg.includes("&lt;b&gt;&amp;") && !svg.includes("<b>&"));
  assert.ok(svg.includes("rotate(-90)"));
  assert.ok(!svg.includes("<rect x="), "a single-text cloud has no comparison legend");
});

test("comparison legend is drawn into the SVG and PDF", () => {
  const items = [{ word: "wind", count: 6, countA: 5, countB: 1, side: "a", tip: "wind: 5 in North, 1 in South", x: 100, y: 40, size: 20, rotate: 0 }];
  const legend = [{ label: "North Energy", color: COMPARE_COLORS.a }, { label: "South Power", color: COMPARE_COLORS.b }];
  const doc = composeDocument(items, { width: 500, cloudHeight: 80, color: (item) => COMPARE_COLORS[item.side], legend });
  const svg = toSVG(doc);
  assert.ok(svg.includes(`fill="${COMPARE_COLORS.a}"`) && svg.includes("North Energy") && svg.includes("South Power"));
  assert.ok(svg.includes("wind: 5 in North, 1 in South"));
  assert.ok(doc.shapes.length === 2);
  const pdf = toPDF(doc, estimateWidth);
  assert.ok(pdf.includes(" re f"));
});

test("PDF is structurally valid with correct cross-reference offsets", () => {
  const items = [{ word: "København (æøå)", count: 3, x: 100, y: 50, size: 20, rotate: 0, textWidth: 150 }];
  const doc = composeDocument(items, { width: 400, cloudHeight: 100, title: "Tæst", color: () => "#173f5f" });
  const pdf = toPDF(doc, estimateWidth);
  assert.ok(pdf.startsWith("%PDF-1.4") && pdf.trimEnd().endsWith("%%EOF"));
  const startxref = Number(pdf.match(/startxref\n(\d+)/)[1]);
  assert.ok(pdf.slice(startxref).startsWith("xref"));
  const offsets = [...pdf.slice(startxref).matchAll(/^(\d{10}) 00000 n $/gm)].map((m) => Number(m[1]));
  offsets.forEach((o, i) => assert.ok(pdf.slice(o).startsWith(`${i + 1} 0 obj`), `object ${i + 1}`));
  assert.ok(pdf.includes("(K\xF8benhavn \\(\xE6\xF8\xE5\\)) Tj"), "WinAnsi bytes and escaped parentheses");
  assert.equal(winAnsi("Ł€"), "?\x80");
});

test("small word clouds are scaled up to fill the frame, without overlaps", () => {
  const tags = ["outlet", "alternative", "media", "outlets", "nordicamo"].map((word, i) => ({ word, count: 7 - i }));
  const size = fontScale(tags, 12, 64);
  const { items } = wordCloudLayout(tags, { width: 900, height: 560, size, measure: estimateWidth });
  const left = Math.min(...items.map((i) => i.x - i.w / 2));
  const right = Math.max(...items.map((i) => i.x + i.w / 2));
  const top = Math.min(...items.map((i) => i.y - i.h / 2));
  const bottom = Math.max(...items.map((i) => i.y + i.h / 2));
  assert.ok(right - left > 900 * 0.8 || bottom - top > 560 * 0.8, "fills at least one dimension");
  assert.ok(left >= 0 && right <= 900 && top >= 0 && bottom <= 560);
  for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) {
    const a = items[i], b = items[j];
    assert.ok(a.x + a.w / 2 <= b.x - b.w / 2 || b.x + b.w / 2 <= a.x - a.w / 2 || a.y + a.h / 2 <= b.y - b.h / 2 || b.y + b.h / 2 <= a.y - a.h / 2);
  }
  assert.ok(Math.abs(items[0].textWidth - estimateWidth(items[0].word, items[0].size)) < 0.01, "text width scales with size");
  assert.deepEqual(fitToFrame([], 100, 100), []);
});
