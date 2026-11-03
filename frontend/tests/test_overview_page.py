import os
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from live_activity import CountryActivity  # noqa: E402

TODAY = date(2026, 9, 26)
OVERVIEW_SOURCE = Path(__file__).resolve().parents[1] / "pages" / "overview.py"


class TestLandingPage(unittest.TestCase):
    def test_cards_and_hero_show_the_week_comparison(self):
        from pages.overview import country_cards_html, hero_html, load_country_activity
        item = CountryActivity("norway", 143, 563, [563, 143], 6, coverage_verified=False)
        for rendered in (country_cards_html([item]), hero_html(item, None, TODAY)):
            self.assertNotIn("Provisional", rendered)
            self.assertNotIn("coverage not verified", rendered)
            self.assertIn("75% vs previous 7 days", rendered)
            self.assertNotIn("collecting daily", rendered)
        self.assertEqual(load_country_activity(TODAY, None), [])

    def test_research_actions_use_the_expected_destinations(self):
        from pages.overview import _research_action_items

        html = _research_action_items()
        for title in ("Compare", "Investigate", "Build a research case"):
            self.assertIn(title, html)
        for page in ("?page=Explorer", "?page=Media", "?page=Workshop"):
            self.assertIn(page, html)

    def test_hero_uses_the_agreed_title_stack(self):
        from pages.overview import hero_html

        html = hero_html(CountryActivity("nordic", 1234, 1000, [], 50), None, TODAY)
        self.assertIn(">Nordicamo</h1>", html)
        self.assertIn("The Nordic Alternative Media Observatory", html)
        self.assertIn("Monitoring alternative news media content", html)
        self.assertIn("1,234", html)
        self.assertIn("50 active outlets", html)
        self.assertIn("Explore the data", html)
        self.assertNotIn("?page=GetAccess", html)

    def test_country_cards_deep_link_into_the_explorer(self):
        from pages.overview import country_cards_html

        html = country_cards_html([CountryActivity("finland", 42, 40, [1, 2, 3], 7)])
        self.assertIn("?page=Explorer&country=finland", html)
        self.assertIn("Finland", html)
        self.assertIn("7 active outlets", html)
        self.assertIn("<svg", html)

    def test_ticker_escapes_repairs_and_labels_countries(self):
        from pages.overview import ticker_html

        html = ticker_html(
            [
                {"domain": "www.a.dk", "title": "<b>x</b>", "url": "https://a.dk/1", "date": "2026-09-25"},
                {"domain": "riks.se", "title": "nÃ¤r", "url": None, "date": "2026-09-24"},
            ],
            {"a.dk": "denmark"},
        )
        self.assertIn("news-ticker-items", html)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", html)
        self.assertIn("(DK)", html)
        self.assertNotIn("Denmark", html)
        self.assertIn("när", html)
        self.assertIn("rel='noopener noreferrer'", html)
        self.assertEqual(ticker_html([], {}), "")

    def test_archive_explains_gap_between_raw_and_clean_totals(self):
        from pages.overview import archive_html

        overview = {
            "total_articles": 763624,
            "total_outlets": 78,
            "date_range": {"earliest": "2008-01-01", "latest": "2026-09-26"},
            "by_country": {"denmark": 1, "finland": 1, "norway": 1, "sweden": 1},
        }
        html = archive_html(overview, 1035950)
        self.assertIn("1,035,950", html)
        self.assertLess(html.index("1,035,950"), html.index("763,624"))
        self.assertIn("analysis-ready", html)
        self.assertIn("2008–2026", html)
        self.assertIn("272,326", html)
        self.assertNotIn("lp-archive-note", archive_html(overview, None))

    def test_landing_uses_clean_overview_not_raw_bundle_for_headline_numbers(self):
        text = OVERVIEW_SOURCE.read_text(encoding="utf-8")
        self.assertIn("overview = fetch_overview()", text)
        self.assertNotIn('landing.get("overview") or fetch_overview()', text)

    def test_ticker_sits_above_the_hero_and_filter_chart_is_gone(self):
        text = OVERVIEW_SOURCE.read_text(encoding="utf-8")
        body = text[text.index("def show_overview_page"):]
        self.assertLess(body.index("ticker_html("), body.index("hero_html("))
        self.assertNotIn("st.slider", text)
        self.assertNotIn("st.selectbox", text)

class TestLandingMobileCss(unittest.TestCase):
    def test_hero_stacks_to_one_column_on_small_screens(self):
        import re
        from pages.overview import LANDING_CSS

        block = LANDING_CSS[LANDING_CSS.index("@media (max-width:900px)"):]
        block = block[:block.index("}\n}") + 3]
        rules = dict(re.findall(r"([^{}]+)\{([^{}]*)\}", block.split("{", 1)[1]))
        hero = next(v for k, v in rules.items() if k.strip() == ".lp-hero")
        self.assertIn("grid-template-columns:1fr", hero)
        # The hero must never share a multi-column rule on small screens.
        for selector, body in rules.items():
            if "repeat(" in body:
                self.assertNotIn(".lp-hero", selector)

    def test_phone_news_bar_runs_slower_than_desktop(self):
        app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        phone = app_source[app_source.index("@media (max-width: 900px)"):]
        phone = phone[:phone.index("@media (max-width: 520px)")]
        self.assertIn("animation-duration: calc(var(--ticker-duration, 40s) * 2.5);", phone)
        overview = OVERVIEW_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("Provisional", overview)
        self.assertNotIn("provisional coverage", overview)


if __name__ == "__main__":
    unittest.main()
