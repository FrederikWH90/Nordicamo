import os
import sys
import unittest
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from workshop_helpers import (  # noqa: E402
    MAX_BROWSER_PREVIEW_ROWS,
    TOPIC_OPTIONS,
    Selection,
    build_access_request_context,
    presets,
    preview_records,
    safe_article_url,
    selection_from_query_params,
    selection_summary_lines,
    teaser_note,
)

FULL = Selection(
    countries=("denmark", "sweden"),
    year_from=2020,
    year_to=2022,
    orientation="Left",
    topics=("Environment, Climate & Energy", "Economy & Labor"),
    outlets=("arbejderen.dk",),
    keywords='klimat* OR "grøn omstilling"',
)


class TestSelectionLinks(unittest.TestCase):
    def test_round_trip_through_a_shared_link(self):
        query = parse_qs(urlparse(FULL.share_url()).query)
        flat = {k: v[0] for k, v in query.items()}
        self.assertEqual(flat["page"], "Workshop")
        self.assertEqual(selection_from_query_params(flat, 2008, 2026), FULL)

    def test_topics_with_commas_survive(self):
        params = FULL.to_query_params()
        self.assertIn("Environment, Climate & Energy", params["t"].split("|"))

    def test_empty_selection_has_only_the_page(self):
        self.assertEqual(Selection().to_query_params(), {"page": "Workshop"})
        self.assertEqual(Selection().api_params(), [])

    def test_untrusted_link_values_are_dropped_or_clamped(self):
        parsed = selection_from_query_params(
            {"c": "denmark,iceland,<script>", "y": "1990-2099", "o": "Centre", "t": "Nope|Economy & Labor", "q": "x" * 500},
            2008,
            2026,
        )
        self.assertEqual(parsed.countries, ("denmark",))
        self.assertEqual((parsed.year_from, parsed.year_to), (2008, 2026))
        self.assertIsNone(parsed.orientation)
        self.assertEqual(parsed.topics, ("Economy & Labor",))
        self.assertEqual(len(parsed.keywords), 200)

    def test_bad_year_range_is_ignored(self):
        parsed = selection_from_query_params({"y": "abc-def"}, 2008, 2026)
        self.assertEqual((parsed.year_from, parsed.year_to), (None, None))

    def test_api_params_repeat_list_filters(self):
        params = FULL.api_params()
        self.assertEqual([v for k, v in params if k == "countries"], ["denmark", "sweden"])
        self.assertIn(("topics", "Environment, Climate & Energy"), params)
        self.assertIn(("date_from", "2020-01-01"), params)
        self.assertIn(("date_to", "2022-12-31"), params)
        self.assertIn(("partisan", "Left"), params)


class TestPresetsAndRequest(unittest.TestCase):
    def test_presets_use_valid_topics_and_years(self):
        items = presets(2026)
        self.assertGreaterEqual(len(items), 4)
        for preset in items:
            self.assertTrue(set(preset.selection.topics) <= set(TOPIC_OPTIONS), preset.key)
            self.assertLessEqual(preset.selection.year_to or 2026, 2026)
            self.assertLessEqual(len(preset.label), 24, "labels must fit on one button line")

    def test_request_text_is_reproducible(self):
        text = build_access_request_context(FULL, {"total": 1234, "teasers": 56})
        self.assertIn("Countries: Denmark, Sweden", text)
        self.assertIn("Matching articles (at time of request): 1,234, of which 56 teaser-only", text)
        self.assertIn("Selection link: https://nordicamo.org/?page=Workshop", text)
        self.assertIn("Purpose and affiliation", text)

    def test_summary_defaults(self):
        lines = dict(selection_summary_lines(Selection()))
        self.assertEqual(lines["Countries"], "All four countries")
        self.assertEqual(lines["Keywords"], "None")

    def test_teaser_note(self):
        self.assertEqual(teaser_note(0, 0), "")
        self.assertEqual(teaser_note(100, 0), "")
        self.assertTrue(teaser_note(100, 12).startswith("12% of these articles are teasers"))


class TestPreviewRows(unittest.TestCase):
    def test_rows_are_metadata_only(self):
        rows = preview_records([{
            "date": "2024-01-01", "country": "denmark", "outlet": "example.dk", "partisan": "Right",
            "categories": ["crime & justice"], "title": "Title", "url": "https://example.dk/a",
            "content": "full text must never appear", "teaser": True,
        }])
        self.assertEqual(rows[0]["Country"], "DK")
        self.assertEqual(rows[0]["Topics"], "Crime & Justice")
        self.assertEqual(rows[0]["Teaser"], "yes")
        self.assertNotIn("full text must never appear", str(rows))

    def test_rows_are_bounded(self):
        self.assertEqual(len(preview_records([{}] * 500)), MAX_BROWSER_PREVIEW_ROWS)

    def test_legacy_category_strings(self):
        self.assertEqual(preview_records([{"categories": '["health & medicine"]'}])[0]["Topics"], "Health & Medicine")
        self.assertEqual(preview_records([{"categories": None}])[0]["Topics"], "Not yet categorized")

    def test_safe_article_url_allows_only_http(self):
        self.assertEqual(safe_article_url("https://example.dk/a"), "https://example.dk/a")
        self.assertEqual(safe_article_url("javascript:alert(1)"), "")
        self.assertEqual(safe_article_url(None), "")


class TestWorkshopPage(unittest.TestCase):
    def test_page_has_one_flow_without_project_picker_or_hidden_steps(self):
        from pathlib import Path

        text = (Path(__file__).resolve().parents[1] / "pages" / "workshop.py").read_text(encoding="utf-8")
        self.assertNotIn("WORKSHOP_PROJECTS", text)
        self.assertNotIn("st.expander", text)
        self.assertIn("Request this dataset", text)
        self.assertIn("share_url()", text)


if __name__ == "__main__":
    unittest.main()
