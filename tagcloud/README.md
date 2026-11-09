# Nordicamo Tag Cloud Generator

`https://tagcloud.nordicamo.org` — paste a text, count its words, and get a tag cloud
or a word cloud, plus SVG, PDF, PNG, CSV, TSV and JSON downloads.

Everything runs in the visitor's browser: the text is never uploaded. No build step,
no dependencies, no external fonts or scripts.

## Options (as in the classic tag cloud generators)

- Minimum number of characters (default 3) and minimum frequency (default 3)
- Stopwords: keep or remove (English, Danish, Swedish, Norwegian, Finnish, German, or all)
- Ordering: by frequency, by term name, or unordered (order of first appearance)
- For the SVG/PDF rendering: method (max 55 characters), query (max 55), title (max 45)
- Word cloud: maximum number of words, horizontal or some vertical words, blue shades or black

## Files

| File | What it does |
|---|---|
| `index.html`, `css/style.css` | The page |
| `js/core.js` | Tokenising, counting, ordering, font sizes |
| `js/layout.js` | Word cloud (spiral packing) and tag cloud (line wrapping) geometry |
| `js/export.js` | CSV/TSV/JSON, SVG and a small dependency-free PDF writer |
| `js/stopwords.js` | Stopword lists |
| `js/app.js` | Wiring the page together |
| `tests/` | Unit tests: `npm test` (Node 20+) |

## Run locally

```bash
cd tagcloud && python3 -m http.server 18040 --bind 127.0.0.1
```

Then open http://127.0.0.1:18040.

## Hosting

nginx serves the files directly from `/var/www/nordicamo-tagcloud`
(site config: `server/tagcloud/tagcloud.nordicamo.org.conf`).

- One-time setup (needs the DNS record and sudo): `sudo bash server/tagcloud/setup_once.sh`
- Publish a new version from `main` (no sudo):
  `cd /home/frede/NAMO_nov25 && git pull --ff-only origin main && ./server/deploy/deploy_tagcloud.sh`
