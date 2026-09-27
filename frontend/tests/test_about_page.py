import os
import re
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pages.about import SECTIONS, body_html, glance_html, toc_html  # noqa: E402

BODY = body_html({"total_outlets": 77, "total_articles": 685808, "date_range": {"earliest": "2008-01-01"}}, "", "")
PLAIN = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", BODY))


class TestAboutContent(unittest.TestCase):
    def test_approved_content_is_kept(self):
        """Edits may condense wording, but every substantive point must stay."""
        for phrase in (
            "comparative platform for studying alternative news media",
            "publisher-operated outlets",
            "not social media accounts",
            "not a complete census",
            "sustained publication activity",
            "clear alternative positioning",
            "Country experts",
            "versioned",
            "Active observatory",
            "Historical data",
            "underrepresented",
            "robots.txt",
            "rate limits and backoff",
            "custom scrapers",
            "Trafilatura",
            "duplicate detection",
            "date verification",
            "not authoritative classifications",
            "descriptive and exploratory",
            "outlet concentration",
            "close reading, case selection and interpretive analysis",
            "politically sensitive material",
            "user-level data",
            "access tiers, logging",
            "aggregated summaries",
            "Carlsberg-funded",
            "Austria and Germany",
        ):
            self.assertIn(phrase, PLAIN, phrase)

    def test_links(self):
        self.assertIn('href="https://digitalmedialab.ruc.dk/"', BODY)
        self.assertIn("<strong>Digital Media Lab (DML)</strong></a> hosts this platform", BODY)
        self.assertIn("Department of Communication and Arts at Roskilde University", BODY)
        self.assertIn("https://github.com/FrederikWH90/Nordicamo", BODY)
        self.assertIn("alternative-media-and-ideological-counterpublics", BODY)


class TestAboutLayout(unittest.TestCase):
    def test_every_menu_link_has_a_section_in_reading_order(self):
        positions = [BODY.index(f"id='{key}'") for key, _ in SECTIONS]
        self.assertEqual(positions, sorted(positions))
        toc = toc_html()
        for key, label in SECTIONS:
            self.assertIn(f"href='#{key}'", toc)
            self.assertIn(label, toc)

    def test_glance_uses_live_numbers_and_hides_without_data(self):
        text = glance_html({"total_outlets": 77, "total_articles": 685808, "date_range": {"earliest": "2008-01-01"}})
        self.assertIn("685,808", text)
        self.assertIn("since 2008", text)
        self.assertEqual(glance_html(None), "")
        # Same outlet count as the Media Archive when the directory is available.
        self.assertIn("<b>77</b>outlets", glance_html({"total_outlets": 78, "total_articles": 1}, outlet_count=77))

    def test_images_are_optional(self):
        self.assertNotIn("<img src=''", BODY)


if __name__ == "__main__":
    unittest.main()
