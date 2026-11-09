// Output formats. Pure functions returning strings/bytes; the page turns
// them into downloads.

export const CLOUD_FONT = "Helvetica, Arial, sans-serif";

export function toDelimited(tags, delimiter = ",", labels = null) {
  const cell = (v) => {
    const s = String(v);
    return /[",\t\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const compared = tags.some((t) => t.countA !== undefined);
  const header = compared
    ? ["word", "frequency", labels?.a || "text_a", labels?.b || "text_b"]
    : ["word", "frequency"];
  const rows = [
    header,
    ...tags.map((t) => (compared ? [t.word, t.count, t.countA ?? 0, t.countB ?? 0] : [t.word, t.count])),
  ];
  return rows.map((r) => r.map(cell).join(delimiter)).join("\n") + "\n";
}

export function toJSON(tags, meta = {}) {
  const rows = tags.map((t) => {
    const row = { word: t.word, frequency: t.count };
    if (t.countA !== undefined) {
      row.text_a = t.countA;
      row.text_b = t.countB ?? 0;
    }
    return row;
  });
  return JSON.stringify({ ...meta, tags: rows }, null, 2) + "\n";
}

const escapeXml = (s) =>
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/**
 * A complete cloud document: optional title on top, the positioned words,
 * and method/query/credit lines at the bottom. `items` come from layout.js.
 * Returns the geometry once, so SVG and PDF draw exactly the same picture.
 */
function legendRows(legend, width, margin) {
  const rows = [];
  let row = [];
  let used = margin;
  for (const item of legend) {
    const label = [...String(item.label ?? "")].slice(0, 28).join("");
    const span = 16 + label.length * 6.4 + 16;
    if (row.length && used + span > width - margin) {
      rows.push(row);
      row = [];
      used = margin;
    }
    row.push({ ...item, label, x: used });
    used += span;
  }
  if (row.length) rows.push(row);
  return rows;
}

export function composeDocument(items, { width, cloudHeight, title = "", method = "", query = "", credit = "", color, legend = [] }) {
  const margin = 28;
  const titleH = title ? 40 : 0;
  const legendRowsDrawn = legendRows(legend, width, margin);
  const legendH = legendRowsDrawn.length ? 8 + legendRowsDrawn.length * 22 : 0;
  const notes = [method && `Method: ${method}`, query && `Query: ${query}`, credit].filter(Boolean);
  const notesH = notes.length ? 14 + notes.length * 16 : 0;
  const height = margin + titleH + cloudHeight + legendH + notesH + margin;
  const texts = [];
  const shapes = [];
  if (title) texts.push({ text: title, x: width / 2, y: margin + 22, size: 22, bold: true, anchor: "middle", color: "#111111" });
  for (const item of items) {
    texts.push({
      text: item.word, x: item.x, y: margin + titleH + item.y, size: item.size, w: item.textWidth ?? null,
      rotate: item.rotate || 0, anchor: "middle", color: color(item), count: item.count,
      tip: item.tip,
    });
  }
  legendRowsDrawn.forEach((row, rowIndex) => {
    const y = margin + titleH + cloudHeight + 10 + rowIndex * 22;
    for (const item of row) {
      shapes.push({ x: item.x, y, w: 12, h: 12, color: item.color });
      texts.push({ text: item.label, x: item.x + 16, y: y + 11, size: 11, anchor: "start", color: "#1f2933" });
    }
  });
  notes.forEach((line, i) => {
    texts.push({
      text: line, x: margin, y: margin + titleH + cloudHeight + legendH + 14 + (i + 1) * 16 - 4,
      size: 11, anchor: "start", color: "#5a6a7a",
    });
  });
  return { width, height, texts, shapes };
}

function shapeSVG(s) {
  if (s.type === "line") {
    const dash = s.dash ? ` stroke-dasharray="${s.dash}"` : "";
    return `<line x1="${s.x1.toFixed(1)}" y1="${s.y1.toFixed(1)}" x2="${s.x2.toFixed(1)}" y2="${s.y2.toFixed(1)}" stroke="${s.color}" stroke-width="1.5"${dash}/>`;
  }
  if (s.type === "circle") {
    const title = s.tip ? `<title>${escapeXml(s.tip)}</title>` : "";
    return `<g>${title}<circle cx="${s.cx.toFixed(1)}" cy="${s.cy.toFixed(1)}" r="${s.r}" fill="${s.color}"/></g>`;
  }
  return `<rect x="${s.x.toFixed(1)}" y="${s.y.toFixed(1)}" width="${s.w}" height="${s.h}" rx="2" fill="${s.color}"/>`;
}

export function toSVG(doc) {
  const shapes = (doc.shapes || []).map(shapeSVG);
  const parts = doc.texts.map((t) => {
    const baseline = t.anchor === "middle" && t.count !== undefined ? t.size * 0.35 : 0;
    const weight = t.bold ? ' font-weight="700"' : "";
    const titleText = t.tip || (t.count !== undefined ? `${t.text}: ${t.count}` : "");
    const title = titleText ? `<title>${escapeXml(titleText)}</title>` : "";
    if (t.rotate) {
      return `<text transform="translate(${t.x.toFixed(1)} ${t.y.toFixed(1)}) rotate(${t.rotate})" x="0" y="${baseline.toFixed(1)}" font-size="${t.size.toFixed(1)}" text-anchor="middle" fill="${t.color}"${weight}>${title}${escapeXml(t.text)}</text>`;
    }
    return `<text x="${t.x.toFixed(1)}" y="${(t.y + baseline).toFixed(1)}" font-size="${t.size.toFixed(1)}" text-anchor="${t.anchor}" fill="${t.color}"${weight}>${title}${escapeXml(t.text)}</text>`;
  });
  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${doc.width}" height="${doc.height}" viewBox="0 0 ${doc.width} ${doc.height}" font-family="${CLOUD_FONT}">
<rect width="100%" height="100%" fill="#ffffff"/>
${shapes.join("\n")}
${parts.join("\n")}
</svg>
`;
}

// --- PDF ---------------------------------------------------------------------
// A small single-page PDF writer: vector text in the built-in Helvetica fonts
// with WinAnsi encoding (covers æ ø å ä ö é ü and other Western European letters;
// characters outside it are written as "?").

const CP1252 = {
  "€": 0x80, "‚": 0x82, "ƒ": 0x83, "„": 0x84, "…": 0x85, "†": 0x86, "‡": 0x87, "ˆ": 0x88, "‰": 0x89, "Š": 0x8a,
  "‹": 0x8b, "Œ": 0x8c, "Ž": 0x8e, "‘": 0x91, "’": 0x92, "“": 0x93, "”": 0x94, "•": 0x95, "–": 0x96, "—": 0x97,
  "˜": 0x98, "™": 0x99, "š": 0x9a, "›": 0x9b, "œ": 0x9c, "ž": 0x9e, "Ÿ": 0x9f,
};

export function winAnsi(text) {
  let out = "";
  for (const ch of String(text)) {
    const code = ch.codePointAt(0);
    let byte = CP1252[ch];
    if (byte === undefined) byte = (code >= 0x20 && code <= 0x7e) || (code >= 0xa0 && code <= 0xff) ? code : 0x3f;
    const c = String.fromCharCode(byte);
    out += c === "\\" || c === "(" || c === ")" ? `\\${c}` : c;
  }
  return out;
}

const rgb = (hex) => {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => (v / 255).toFixed(3)).join(" ");
};

/** Returns the PDF as a binary string (one char = one byte). */
export function toPDF(doc, measure) {
  const H = doc.height;
  const ops = ["1 1 1 rg", `0 0 ${doc.width} ${H} re f`];
  for (const s of doc.shapes || []) {
    if (s.type === "line") {
      const dash = s.dash ? "[2 4] 0 d" : "[] 0 d";
      ops.push(`${rgb(s.color)} RG ${dash} 1.25 w ${s.x1.toFixed(2)} ${(H - s.y1).toFixed(2)} m ${s.x2.toFixed(2)} ${(H - s.y2).toFixed(2)} l S [] 0 d`);
    } else if (s.type === "circle") {
      ops.push(`${rgb(s.color)} rg ${s.cx.toFixed(2)} ${(H - s.cy).toFixed(2)} ${s.r} 0 360 arc f`);
    } else {
      ops.push(`${rgb(s.color)} rg ${s.x.toFixed(2)} ${(H - s.y - s.h).toFixed(2)} ${s.w} ${s.h} re f`);
    }
  }
  for (const t of doc.texts) {
    const font = t.bold ? "/F2" : "/F1";
    const width = t.w ?? measure(t.text, t.size);
    const baseline = t.anchor === "middle" && t.count !== undefined ? t.size * 0.35 : 0;
    let m;
    if (t.rotate === -90) {
      // Reads bottom to top, centred on (x, y).
      m = `0 1 -1 0 ${(t.x + baseline).toFixed(2)} ${(H - (t.y + width / 2)).toFixed(2)}`;
    } else {
      const left = t.anchor === "middle" ? t.x - width / 2 : t.x;
      m = `1 0 0 1 ${left.toFixed(2)} ${(H - (t.y + baseline)).toFixed(2)}`;
    }
    ops.push(`BT ${font} ${t.size.toFixed(2)} Tf ${rgb(t.color)} rg ${m} Tm (${winAnsi(t.text)}) Tj ET`);
  }
  const content = ops.join("\n");
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${doc.width} ${H}] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
  ];
  let pdf = "%PDF-1.4\n%\xE2\xE3\xCF\xD3\n";
  const offsets = [];
  objects.forEach((body, i) => {
    offsets.push(pdf.length);
    pdf += `${i + 1} 0 obj\n${body}\nendobj\n`;
  });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  pdf += offsets.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("");
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return pdf;
}

export function binaryStringToBytes(s) {
  const bytes = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) bytes[i] = s.charCodeAt(i) & 0xff;
  return bytes;
}
