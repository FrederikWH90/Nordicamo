// Geometry for the two cloud styles. Pure functions; text width comes from an
// injected `measure(word, fontSize)` so the browser can use real font metrics
// and the tests can use a simple estimate.

// Height of a text line box relative to font size (measured in browsers for
// Helvetica/Arial: 0.92 above the baseline, 0.23 below).
export const LINE_BOX = 1.15;

// Deterministic pseudo-random numbers, so the same text gives the same cloud.
export function seededRandom(seed = 1) {
  let s = seed >>> 0 || 1;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

const overlaps = (a, b, pad) =>
  a.x - a.w / 2 - pad < b.x + b.w / 2 && b.x - b.w / 2 - pad < a.x + a.w / 2 &&
  a.y - a.h / 2 - pad < b.y + b.h / 2 && b.y - b.h / 2 - pad < a.y + a.h / 2;

/**
 * Word cloud: largest words first, each placed on an Archimedean spiral from
 * the centre at the first spot that doesn't overlap an earlier word.
 * Words that can't fit are shrunk a little and retried, then skipped.
 * rotation: "none" | "some" (about one in four words vertical).
 */
export function wordCloudLayout(tags, { width, height, size, measure, rotation = "none", padding = 3, seed = 7 }) {
  const random = seededRandom(seed);
  const placed = [];
  const skipped = [];
  const sorted = [...tags].sort((a, b) => b.count - a.count || a.word.localeCompare(b.word));
  const aspect = width / height;
  for (const tag of sorted) {
    const vertical = rotation === "some" && placed.length > 0 && random() < 0.25;
    let fontSize = size(tag.count);
    let spot = null;
    for (let attempt = 0; attempt < 4 && !spot; attempt++) {
      const textW = measure(tag.word, fontSize);
      const textH = fontSize * LINE_BOX;
      const box = { w: vertical ? textH : textW, h: vertical ? textW : textH };
      if (box.w > width || box.h > height) { fontSize *= 0.85; continue; }
      const start = random() * Math.PI * 2;
      for (let t = 0; t < 2400; t += 0.35) {
        const r = 2.2 * t;
        const candidate = {
          ...box,
          x: width / 2 + r * Math.cos(t + start) * Math.sqrt(aspect),
          y: height / 2 + r * Math.sin(t + start) / Math.sqrt(aspect),
        };
        if (candidate.x - box.w / 2 < 0 || candidate.x + box.w / 2 > width ||
            candidate.y - box.h / 2 < 0 || candidate.y + box.h / 2 > height) {
          if (r > Math.max(width, height)) break;
          continue;
        }
        if (!placed.some((p) => overlaps(candidate, p, padding))) { spot = candidate; break; }
      }
      if (!spot) fontSize *= 0.85;
    }
    if (spot) placed.push({ ...tag, ...spot, size: fontSize, rotate: vertical ? -90 : 0, textWidth: measure(tag.word, fontSize) });
    else skipped.push(tag);
  }
  return { items: fitToFrame(placed, width, height), skipped };
}

/**
 * Scale a finished cloud up (never down) so it fills the frame, keeping it
 * centred. Uniform scaling keeps every gap, so no new overlaps appear.
 */
export function fitToFrame(items, width, height, { margin = 10, maxScale = 3 } = {}) {
  if (!items.length) return items;
  const left = Math.min(...items.map((i) => i.x - i.w / 2));
  const right = Math.max(...items.map((i) => i.x + i.w / 2));
  const top = Math.min(...items.map((i) => i.y - i.h / 2));
  const bottom = Math.max(...items.map((i) => i.y + i.h / 2));
  const scale = Math.min(maxScale, (width - 2 * margin) / (right - left), (height - 2 * margin) / (bottom - top));
  if (!(scale > 1)) return items;
  const cx = (left + right) / 2;
  const cy = (top + bottom) / 2;
  return items.map((i) => ({
    ...i,
    x: width / 2 + (i.x - cx) * scale,
    y: height / 2 + (i.y - cy) * scale,
    w: i.w * scale, h: i.h * scale, size: i.size * scale, textWidth: i.textWidth * scale,
  }));
}

/**
 * Tag cloud: words in the chosen order, flowing left to right in centred lines
 * like text. Used for the SVG/PDF versions of the classic tag cloud.
 */
export function tagCloudLayout(tags, { width, size, measure, gap = 14, lineGap = 6, top = 0 }) {
  const lines = [];
  let line = [];
  let lineWidth = 0;
  for (const tag of tags) {
    const fontSize = size(tag.count);
    const w = measure(tag.word, fontSize);
    if (line.length && lineWidth + gap + w > width) {
      lines.push({ items: line, width: lineWidth });
      line = [];
      lineWidth = 0;
    }
    line.push({ ...tag, size: fontSize, w, h: fontSize * LINE_BOX, textWidth: w });
    lineWidth += (line.length > 1 ? gap : 0) + w;
  }
  if (line.length) lines.push({ items: line, width: lineWidth });

  const items = [];
  let y = top;
  for (const { items: row, width: rowWidth } of lines) {
    const rowHeight = Math.max(...row.map((i) => i.h));
    let x = (width - rowWidth) / 2;
    for (const item of row) {
      // Align words on a shared baseline, like text.
      items.push({ ...item, x: x + item.w / 2, y: y + rowHeight - item.h / 2, rotate: 0 });
      x += item.w + gap;
    }
    y += rowHeight + lineGap;
  }
  return { items, height: Math.max(0, y - lineGap - top) };
}

const boxesOverlap = (a, b, pad = 1) =>
  a.x < b.x + b.w + pad && b.x < a.x + a.w + pad && a.y < b.y + b.h + pad && b.y < a.y + a.h + pad;

/**
 * Comparison plot. X is the word's share of the first text, Y its share of the
 * second. Both axes use the same scale, so the diagonal from (0, 0) to the
 * upper right is equal share. A word used only in the first text sits on the
 * bottom axis; a word used only in the second sits on the left axis.
 */
export function comparisonPlot(tags, {
  width = 900,
  height = 640,
  marginLeft = 64,
  marginRight = 36,
  marginTop = 36,
  marginBottom = 56,
  labelLimit = 40,
} = {}) {
  const maxR = Math.max(1e-12, ...tags.map((t) => Math.max(t.rateA || 0, t.rateB || 0)));
  const origin = { x: marginLeft, y: height - marginBottom };
  const xEnd = { x: width - marginRight, y: origin.y };
  const yEnd = { x: origin.x, y: marginTop };
  const spanX = xEnd.x - origin.x;
  const spanY = origin.y - yEnd.y;
  const X = (rate) => origin.x + (rate / maxR) * spanX;
  const Y = (rate) => origin.y - (rate / maxR) * spanY;
  const points = tags.map((t) => ({
    ...t,
    rateA: t.rateA || 0,
    rateB: t.rateB || 0,
    x: X(t.rateA || 0),
    y: Y(t.rateB || 0),
  }));
  const score = (p) => Math.abs(p.rateA - p.rateB) + 0.25 * (p.rateA + p.rateB);
  const ranked = [...points].sort((a, b) => score(b) - score(a) || b.count - a.count || a.word.localeCompare(b.word));
  const want = new Set(ranked.slice(0, Math.min(labelLimit, ranked.length)).map((p) => p.word));
  const taken = [];
  const labels = new Map();
  for (const p of ranked) {
    if (!want.has(p.word)) continue;
    const textW = Math.max(28, [...p.word].length * 7.2);
    const textH = 13;
    const options = [[8, -3], [8, 12], [-textW - 6, -3], [8, -16], [-textW - 6, 12], [8, 24], [-textW - 6, -16]];
    for (const [dx, dy] of options) {
      const box = { x: p.x + dx, y: p.y + dy - textH + 3, w: textW, h: textH };
      if (box.x < 2 || box.y < 2 || box.x + box.w > width - 2 || box.y + box.h > height - 2) continue;
      if (taken.some((b) => boxesOverlap(box, b))) continue;
      taken.push(box);
      labels.set(p.word, { labelX: box.x, labelY: box.y + textH - 3, labeled: true });
      break;
    }
  }
  return {
    width, height, maxR, origin, xEnd, yEnd,
    diagonal: { x1: origin.x, y1: origin.y, x2: xEnd.x, y2: yEnd.y },
    points: points.map((p) => ({ ...p, ...(labels.get(p.word) || { labeled: false }) })),
  };
}

// Estimate for environments without font metrics (tests, fallback).
export const estimateWidth = (word, fontSize) => [...word].length * fontSize * 0.56;
