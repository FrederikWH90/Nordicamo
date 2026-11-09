import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tagcloud_embed import LEAF_MODULES, TAGCLOUD_DIR, build_embedded_html  # noqa: E402


class TestTagcloudEmbed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = build_embedded_html()

    def test_self_contained(self):
        # No relative files: the iframe has no URL to resolve them against.
        self.assertNotIn('src="js/app.js"', self.html)
        self.assertNotIn('href="css/style.css"', self.html)
        self.assertNotIn('rel="icon"', self.html)
        self.assertIn("<style>", self.html)
        self.assertIn("--brick: #8c342f", self.html)

    def test_all_modules_embedded_and_imports_rewired(self):
        for name in (*LEAF_MODULES, "app.js"):
            self.assertIn(f'"{name}"', self.html, name)
        # Every relative import in app.js is one the loader can rewire.
        app = (TAGCLOUD_DIR / "js" / "app.js").read_text(encoding="utf-8")
        imports = set(re.findall(r'from "\./([\w-]+\.js)"', app))
        self.assertEqual(imports, set(LEAF_MODULES))
        # Leaf modules must stay import-free, or the loader would need ordering.
        for name in LEAF_MODULES:
            self.assertNotRegex((TAGCLOUD_DIR / "js" / name).read_text(encoding="utf-8"), r"^import ", name)

    def test_script_content_cannot_close_the_script_element(self):
        # Only a literal "</script" can end a script element early. The embedded
        # sources contain none (they are escaped), so the page has exactly one:
        # the loader's own closing tag.
        sources_json = self.html[self.html.index("const sources ="): self.html.index("const urls")]
        self.assertNotIn("</", sources_json)
        self.assertEqual(len(re.findall(r"</script", self.html, re.IGNORECASE)), 1)

    def test_policy_still_blocks_network_access(self):
        self.assertIn("connect-src 'none'", self.html)
        self.assertIn('<base target="_blank">', self.html)

    def test_page_file_is_served_at_wordcloudtest(self):
        page = Path(__file__).resolve().parents[1] / "pages" / "wordcloudtest.py"
        self.assertTrue(page.exists())
        self.assertIn("build_embedded_html", page.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
