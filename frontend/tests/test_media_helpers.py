import os
import sys
import unittest
from datetime import date
from urllib.parse import parse_qs

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from media_helpers import (  # noqa: E402
    average_per_month,
    coverage_years,
    filter_directory,
    normalize_outlet,
    outlet_status,
    profile_url,
    sort_directory,
    status_line,
    teaser_share,
    time_ago,
    workshop_url,
)

TODAY = date(2026, 9, 27)
OUTLETS = [
    {"outlet": "document.no", "name": "Document", "country": "norway", "partisan": "Right",
     "articles": 107162, "teasers": 76605, "last_30_days": 960, "first_date": "2008-01-01", "last_date": "2026-09-25"},
    {"outlet": "arbejderen.dk", "name": "Arbejderen", "country": "denmark", "partisan": "Left",
     "articles": 9297, "teasers": 0, "last_30_days": 139, "first_date": "2012-09-08", "last_date": "2026-09-25"},
    {"outlet": "old.se", "name": "Old Outlet", "country": "sweden", "partisan": "Other",
     "articles": 500, "teasers": 0, "last_30_days": 0, "first_date": "2010-01-01", "last_date": "2019-03-01"},
    {"outlet": "slow.fi", "name": "Slow", "country": "finland", "partisan": "Right",
     "articles": 900, "teasers": 0, "last_30_days": 0, "first_date": "2020-01-01", "last_date": "2026-07-01"},
]


class TestStatus(unittest.TestCase):
    def test_status_thresholds(self):
        self.assertEqual(outlet_status("2026-09-25", TODAY), "Active")
        self.assertEqual(outlet_status("2026-07-01", TODAY), "Quiet")
        self.assertEqual(outlet_status("2019-03-01", TODAY), "Historical")
        self.assertEqual(outlet_status(None, TODAY), "Historical")

    def test_time_ago(self):
        self.assertEqual(time_ago("2026-09-27", TODAY), "today")
        self.assertEqual(time_ago("2026-09-26", TODAY), "yesterday")
        self.assertEqual(time_ago("2026-09-25", TODAY), "2 days ago")
        self.assertEqual(time_ago("2026-09-01", TODAY), "3 weeks ago")
        self.assertEqual(time_ago("2019-03-01", TODAY), "Mar 2019")
        self.assertEqual(time_ago("bad", TODAY), "unknown")

    def test_status_line(self):
        self.assertEqual(status_line(OUTLETS[0], TODAY), ("Active", "last article 2 days ago"))


class TestDirectory(unittest.TestCase):
    def test_search_matches_name_and_domain(self):
        self.assertEqual([o["outlet"] for o in filter_directory(OUTLETS, TODAY, query="docu")], ["document.no"])
        self.assertEqual([o["outlet"] for o in filter_directory(OUTLETS, TODAY, query="ARBEJDEREN.DK")], ["arbejderen.dk"])

    def test_filters_combine(self):
        result = filter_directory(OUTLETS, TODAY, countries=["norway", "finland"], orientation="Right", status="Quiet")
        self.assertEqual([o["outlet"] for o in result], ["slow.fi"])
        self.assertEqual(len(filter_directory(OUTLETS, TODAY, orientation="All", status="All")), 4)

    def test_sorts(self):
        self.assertEqual(sort_directory(list(OUTLETS), "Most articles")[0]["outlet"], "document.no")
        self.assertEqual(sort_directory(list(OUTLETS), "Name (A–Z)")[0]["outlet"], "arbejderen.dk")
        self.assertEqual(sort_directory(list(OUTLETS), "Latest article")[-1]["outlet"], "old.se")
        self.assertEqual(sort_directory(list(OUTLETS), "Most active now")[0]["outlet"], "document.no")


class TestFormatting(unittest.TestCase):
    def test_coverage_teasers_average(self):
        self.assertEqual(coverage_years(OUTLETS[0]), "2008–2026")
        self.assertEqual(coverage_years({"first_date": None}), "—")
        self.assertAlmostEqual(teaser_share(OUTLETS[0]), 76605 / 107162)
        self.assertEqual(teaser_share({"articles": 0}), 0.0)
        self.assertEqual(average_per_month([10, 20]), 15)
        self.assertEqual(average_per_month([]), 0.0)

    def test_links(self):
        self.assertEqual(parse_qs(profile_url("document.no")[1:]), {"page": ["Media"], "media": ["document.no"]})
        params = parse_qs(workshop_url(OUTLETS[0], TODAY)[1:])
        self.assertEqual(params["out"], ["document.no"])
        self.assertEqual(params["y"], ["2008-2026"])

    def test_normalize_outlet(self):
        self.assertEqual(normalize_outlet("https://www.Document.no/"), "document.no")
        self.assertEqual(normalize_outlet(None), "")


class TestMediaPage(unittest.TestCase):
    def test_directory_uses_links_not_per_card_buttons(self):
        from pathlib import Path

        text = (Path(__file__).resolve().parents[1] / "pages" / "media.py").read_text(encoding="utf-8")
        self.assertNotIn("st.button", text)
        self.assertNotIn("fetch_articles_search", text)  # no more downloading 500 full articles
        self.assertIn("In their own words", text)

    def test_card_escapes_outlet_values(self):
        from pages.media import _card

        card = _card({"outlet": "x.dk", "name": "<script>", "country": "denmark", "partisan": "Left",
                      "articles": 1, "monthly_12": [1, 2], "last_date": "2026-09-25"}, TODAY)
        self.assertNotIn("<script>", card)
        self.assertIn("?page=Media&amp;media=x.dk", card)


if __name__ == "__main__":
    unittest.main()
