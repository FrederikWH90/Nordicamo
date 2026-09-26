import os
import sys
import unittest
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestExplorerState(unittest.TestCase):
    def test_modes_and_countries_normalise(self):
        from pages.explorer import MODE_COMPARE, MODE_DEEP_DIVE, normalize_country, normalize_explorer_mode

        self.assertEqual(normalize_explorer_mode("bad"), MODE_COMPARE)
        self.assertEqual(normalize_explorer_mode(MODE_DEEP_DIVE), MODE_DEEP_DIVE)
        self.assertEqual(normalize_country("iceland"), "denmark")
        self.assertEqual(normalize_country("norway"), "norway")

    def test_country_view_to_state(self):
        from pages.explorer import COUNTRY_VIEW_COMPARE, MODE_COMPARE, MODE_DEEP_DIVE, country_view_to_state

        self.assertEqual(country_view_to_state(COUNTRY_VIEW_COMPARE), (MODE_COMPARE, None))
        self.assertEqual(country_view_to_state("Finland"), (MODE_DEEP_DIVE, "finland"))
        self.assertEqual(country_view_to_state(None), (MODE_COMPARE, None))

    def test_country_view_summary_names_the_selected_country(self):
        from pages.explorer import COUNTRY_VIEW_COMPARE, country_view_summary

        self.assertIn("across the Nordic region", country_view_summary(COUNTRY_VIEW_COMPARE))
        for view, adjective in [("Denmark", "danish"), ("Finland", "finnish"), ("Norway", "norwegian"), ("Sweden", "swedish")]:
            self.assertIn(f"{adjective} alternative media landscape", country_view_summary(view).lower())

    def test_orientation_filter_and_labels(self):
        from pages.explorer import _default_year_range, _partisan_label, orientation_to_filter

        self.assertIsNone(orientation_to_filter("All"))
        self.assertEqual(orientation_to_filter("Left"), "Left")
        self.assertEqual(_partisan_label(None), "All orientations")
        self.assertEqual(_default_year_range(2008, 2026), (2016, 2026))
        self.assertEqual(_default_year_range(2020, 2022), (2020, 2022))

    def test_nothing_is_hidden_behind_toggles_or_expanders(self):
        from pathlib import Path

        text = (Path(__file__).resolve().parents[1] / "pages" / "explorer.py").read_text(encoding="utf-8")
        self.assertNotIn("st.toggle", text)
        self.assertNotIn("st.expander", text)
        self.assertNotIn("st.radio", text)


class TestExplorerTransforms(unittest.TestCase):
    def test_monthly_frame_drops_current_month(self):
        from explorer_data import monthly_frame

        frame = monthly_frame(
            [{"date": "2026-08", "count": 5}, {"date": "2026-09", "count": 2}, {"date": "2026-07", "count": "3"}],
            today=date(2026, 9, 26),
        )
        self.assertEqual(frame["count"].tolist(), [3, 5])

    def test_outlet_shares_merge_www_variants(self):
        from explorer_data import outlet_shares, top_n_share

        shares = outlet_shares([
            {"domain": "www.document.dk", "partisan": "Right", "count": 60},
            {"domain": "document.dk", "partisan": "Right", "count": 20},
            {"domain": "arbejderen.dk", "partisan": "Left", "count": 20},
        ])
        self.assertEqual(shares["outlet"].tolist(), ["document.dk", "arbejderen.dk"])
        self.assertAlmostEqual(shares["share"].iloc[0], 0.8)
        self.assertAlmostEqual(top_n_share(shares, 1), 0.8)
        self.assertTrue(outlet_shares([]).empty)

    def test_concentration_segments_fold_the_rest(self):
        from explorer_data import concentration_segments, outlet_shares

        shares = outlet_shares([{"domain": f"{i}.se", "count": 10} for i in range(7)])
        segments = concentration_segments({"sweden": shares}, top=5)
        self.assertEqual(len(segments), 6)
        self.assertEqual(segments.iloc[-1]["segment"], "All other outlets")
        self.assertAlmostEqual(segments["share"].sum(), 1.0)

    def test_orientation_mix(self):
        from explorer_data import orientation_mix, outlet_shares

        mix = orientation_mix(outlet_shares([
            {"domain": "a", "partisan": "Right", "count": 3},
            {"domain": "b", "partisan": "Left", "count": 1},
        ]))
        self.assertEqual(list(mix), ["Right", "Left"])
        self.assertAlmostEqual(mix["Right"], 0.75)

    def test_topic_share_by_year_is_share_of_articles_and_skips_small_years(self):
        from explorer_data import topic_share_by_year

        frame = topic_share_by_year(
            [
                {"date": "2024", "category": "Crime & Justice", "count": 100},
                {"date": "2024", "category": "Other", "count": 50},
                {"date": "2025", "category": "Crime & Justice", "count": 10},
            ],
            [{"date": "2024", "count": 400}, {"date": "2025", "count": 50}],
            min_base=200,
        )
        self.assertEqual(frame.to_dict("records"), [{"year": 2024, "topic": "Crime & Justice", "share": 0.25, "base": 400}])

    def test_topic_profile_and_matrix(self):
        from explorer_data import profile_matrix, topic_gap_sentence, topic_profile

        dk = topic_profile([{"category": "A", "count": 300}, {"category": "B", "count": 100}], 1000)
        se = topic_profile([{"category": "A", "count": 100}, {"category": "B", "count": 500}], 1000)
        self.assertEqual(dk, {"A": 0.3, "B": 0.1})
        self.assertEqual(topic_profile([{"category": "A", "count": 1}], 10), {})
        matrix = profile_matrix({"denmark": dk, "sweden": se})
        self.assertEqual(list(matrix.index), ["B", "A"])
        sentence = topic_gap_sentence(matrix)
        self.assertIn("B appears in 50% of Sweden's articles (others: 10%)", sentence)

    def test_outlet_activity_matrix_zero_fills_months(self):
        from explorer_data import outlet_activity_matrix

        matrix = outlet_activity_matrix(
            [
                {"date": "2026-01", "outlet": "www.a.dk", "count": 4},
                {"date": "2026-03", "outlet": "b.dk", "count": 2},
                {"date": "2026-09", "outlet": "b.dk", "count": 9},
            ],
            ["a.dk", "b.dk"],
            today=date(2026, 9, 26),
        )
        self.assertEqual(list(matrix.index), ["a.dk", "b.dk"])
        self.assertEqual(matrix.shape[1], 3)
        self.assertEqual(matrix.loc["a.dk"].tolist(), [4, 0, 0])

    def test_concentration_sentence(self):
        from explorer_data import concentration_sentence, outlet_shares

        text = concentration_sentence({
            "norway": outlet_shares([{"domain": "a", "count": 90}, {"domain": "b", "count": 10}]),
            "sweden": outlet_shares([{"domain": f"{i}", "count": 10} for i in range(10)]),
        })
        self.assertIn("100% of all articles in Norway", text)
        self.assertIn("30% in Sweden", text)


class TestExplorerFigures(unittest.TestCase):
    def _valid(self, fig):
        fig.to_json()  # raises on invalid properties
        return fig

    def test_all_figures_build_with_valid_properties(self):
        from explorer_data import concentration_segments, outlet_activity_matrix, outlet_shares, profile_matrix
        from pages.explorer import (
            activity_heatmap_figure,
            concentration_figure,
            orientation_area_figure,
            orientation_bars_figure,
            outlet_bars_figure,
            share_heatmap_figure,
            topic_trends_figure,
            volume_lines_figure,
        )

        monthly = pd.DataFrame({"date": pd.to_datetime(["2026-01-01", "2026-02-01"]), "count": [3, 4]})
        shares = outlet_shares([{"domain": "a.dk", "partisan": "Right", "count": 5}, {"domain": "b.dk", "partisan": "Left", "count": 2}])
        trends = pd.DataFrame({"year": [2025, 2026], "topic": ["A", "A"], "share": [0.1, 0.2], "base": [500, 500]})

        self._valid(volume_lines_figure({"denmark": monthly}, {"denmark": "#c8102e"}))
        self._valid(orientation_area_figure({"Right": monthly, "Left": monthly}))
        self._valid(concentration_figure(concentration_segments({"denmark": shares})))
        self._valid(orientation_bars_figure({"denmark": {"Right": 0.7, "Left": 0.3}}))
        self._valid(share_heatmap_figure(profile_matrix({"denmark": {"A": 0.2}, "sweden": {"A": 0.4}}), wrap_columns=True))
        self._valid(outlet_bars_figure(shares))
        self._valid(activity_heatmap_figure(outlet_activity_matrix(
            [{"date": "2026-01", "outlet": "a.dk", "count": 2}], ["a.dk"], today=date(2026, 9, 1))))
        fig = self._valid(topic_trends_figure({"denmark": trends, "nordic": trends}, {"denmark": "#c8102e"}, ["A", "B"], dashed={"nordic"}))
        self.assertEqual(sum(1 for t in fig.data if t.showlegend), 2)


if __name__ == "__main__":
    unittest.main()
