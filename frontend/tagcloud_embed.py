"""Build a single self-contained HTML document from the tagcloud/ folder.

Streamlit can only show custom JavaScript inside an iframe (components.html),
which has no URL of its own for relative files. So the stylesheet is inlined,
and the JavaScript modules are loaded from blob: URLs created in the page:
the dependency-free modules first, then app.js with its imports pointed at
those blobs. The tool's code stays in one place (tagcloud/).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

TAGCLOUD_DIR = Path(__file__).resolve().parent.parent / "tagcloud"
LEAF_MODULES = ("core.js", "stopwords.js", "layout.js", "export.js", "example.js")

# Inline scripts and blob: modules need a different policy than the hosted
# site; the page still cannot send data anywhere (connect-src 'none').
EMBED_CSP = (
    "default-src 'none'; script-src 'unsafe-inline' blob:; style-src 'unsafe-inline'; "
    "img-src blob: data:; font-src 'none'; connect-src 'none'; object-src 'none'; "
    "base-uri 'none'; form-action 'none'"
)

LOADER = """
<script>
(async () => {
  const sources = __SOURCES__;
  const urls = {};
  for (const name of __LEAVES__) {
    urls[name] = URL.createObjectURL(new Blob([sources[name]], { type: "text/javascript" }));
  }
  const app = sources["app.js"].replace(/from "\\.\\/([\\w-]+\\.js)"/g, (m, name) => `from "${urls[name]}"`);
  await import(URL.createObjectURL(new Blob([app], { type: "text/javascript" })));
})().catch((err) => {
  document.body.insertAdjacentHTML("afterbegin", "<p style='color:#9a3412;padding:12px'>The word cloud tool could not start.</p>");
  console.error(err);
});
</script>
"""


def _script_json(value) -> str:
    """JSON safe to place inside a <script> element."""
    return json.dumps(value).replace("</", "<\\/").replace("<!--", "<\\!--")


def build_embedded_html(tagcloud_dir: Path = TAGCLOUD_DIR) -> str:
    html = (tagcloud_dir / "index.html").read_text(encoding="utf-8")
    css = (tagcloud_dir / "css" / "style.css").read_text(encoding="utf-8")
    sources = {name: (tagcloud_dir / "js" / name).read_text(encoding="utf-8") for name in (*LEAF_MODULES, "app.js")}

    html = re.sub(r'<meta http-equiv="Content-Security-Policy"[^>]*>',
                  f'<meta http-equiv="Content-Security-Policy" content="{EMBED_CSP}">', html)
    # Streamlit's iframe sandbox allows popups but not top navigation, so
    # links (nordicamo.org, RUC) open in a new tab instead of inside the frame.
    html = html.replace("<head>", '<head>\n<base target="_blank">', 1)
    html = re.sub(r'<link rel="icon"[^>]*>\n?', "", html)
    html = html.replace('<link rel="stylesheet" href="css/style.css">', f"<style>\n{css}\n</style>")
    loader = LOADER.replace("__SOURCES__", _script_json(sources)).replace("__LEAVES__", _script_json(list(LEAF_MODULES)))
    html = html.replace('<script type="module" src="js/app.js"></script>', loader)
    return html
