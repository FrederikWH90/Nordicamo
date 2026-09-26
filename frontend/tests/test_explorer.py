import os
import sys
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestExplorerHelpers(unittest.TestCase):
    def test_normalize_explorer_mode_defaults_to_compare(self):
        from pages.explorer import MODE_COMPARE, normalize_explorer_mode

        self.assertEqual(normalize_explorer_mode(None), MODE_COMPARE)
        self.assertEqual(normalize_explorer_mode("unknown"), MODE_COMPARE)

    def test_normalize_explorer_mode_accepts_valid_values(self):
        from pages.explorer import MODE_COMPARE, MODE_DEEP_DIVE, normalize_explorer_mode

        self.assertEqual(normalize_explorer_mode(MODE_COMPARE), MODE_COMPARE)
        self.assertEqual(normalize_explorer_mode(MODE_DEEP_DIVE), MODE_DEEP_DIVE)

    def test_normalize_country_defaults_to_denmark(self):
        from pages.explorer import normalize_country

        self.assertEqual(normalize_country(None), "denmark")
        self.assertEqual(normalize_country("x"), "denmark")

    def test_normalize_country_accepts_supported_country(self):
        from pages.explorer import normalize_country

        self.assertEqual(normalize_country("sweden"), "sweden")

    def test_country_landscape_label(self):
        from pages.explorer import country_landscape_label

        self.assertEqual(country_landscape_label("denmark"), "Danish Alternative Media Landscape")
        self.assertEqual(country_landscape_label("sweden"), "Swedish Alternative Media Landscape")

    def test_recent_years_returns_last_four_years(self):
        from pages.explorer import recent_years

        self.assertEqual(recent_years(2026), [2023, 2024, 2025, 2026])

    def test_country_year_label_wraps_country_and_year(self):
        from pages.explorer import country_year_label

        self.assertEqual(country_year_label("denmark", 2026), "Denmark<br>2026")

    def test_country_year_multicategory_axis_groups_years_under_country(self):
        from pages.explorer import country_year_axis_pairs, country_year_multicategory_axis

        pairs = country_year_axis_pairs(["denmark", "sweden"], [2025, 2026])
        self.assertEqual(
            pairs,
            [("Denmark", "2025"), ("Denmark", "2026"), ("Sweden", "2025"), ("Sweden", "2026")],
        )
        self.assertEqual(
            country_year_multicategory_axis(pairs),
            [["Denmark", "Denmark", "Sweden", "Sweden"], ["2025", "2026", "2025", "2026"]],
        )

    def test_country_orientation_entities_use_country_then_orientation_order(self):
        from pages.explorer import (
            country_orientation_axis_labels,
            country_orientation_multicategory_axis,
            country_orientation_entities,
            normalize_country_orientation_entity,
        )

        self.assertEqual(normalize_country_orientation_entity("sweden - left"), "Sweden - Left")
        entities = country_orientation_entities(
            ["sweden - other", "denmark - right", "sweden - left", "denmark - left"]
        )
        self.assertEqual(
            entities,
            ["Denmark - Left", "Denmark - Right", "Sweden - Left", "Sweden - Other"],
        )
        self.assertEqual(
            country_orientation_axis_labels(["Denmark - Left", "Sweden - Other"]),
            ["Denmark<br>Left", "Sweden<br>Other"],
        )
        self.assertEqual(
            country_orientation_multicategory_axis(["Denmark - Left", "Denmark - Right"]),
            [["Denmark", "Denmark"], ["Left", "Right"]],
        )

    def test_country_view_to_state(self):
        from pages.explorer import (
            COUNTRY_VIEW_COMPARE,
            MODE_COMPARE,
            MODE_DEEP_DIVE,
            country_view_summary,
            country_view_to_state,
            normalize_country_view,
        )

        self.assertEqual(normalize_country_view("bad"), COUNTRY_VIEW_COMPARE)
        self.assertEqual(country_view_to_state(COUNTRY_VIEW_COMPARE), (MODE_COMPARE, None))
        self.assertEqual(country_view_to_state("Denmark"), (MODE_DEEP_DIVE, "denmark"))
        self.assertIn("across the Nordic region", country_view_summary(COUNTRY_VIEW_COMPARE))
        self.assertIn("danish alternative media landscape", country_view_summary("Denmark").lower())
        self.assertIn("finnish alternative media landscape", country_view_summary("Finland").lower())
        self.assertIn("norwegian alternative media landscape", country_view_summary("Norway").lower())
        self.assertIn("swedish alternative media landscape", country_view_summary("Sweden").lower())

    def test_deep_dive_view_options_use_question_oriented_labels(self):
        from pages.explorer import deep_dive_view_options

        options = deep_dive_view_options()
        self.assertIn("Topic development", options)
        self.assertEqual(options[0], "Publication volume")
        self.assertIn("Outlet drivers", options)

    def test_default_year_range_prefers_2016_2026(self):
        from pages.explorer import _default_year_range

        self.assertEqual(_default_year_range(2008, 2028), (2016, 2026))
        self.assertEqual(_default_year_range(2020, 2024), (2020, 2024))

    def test_topics_metric_transform_share_mode(self):
        from pages.explorer import topics_metric_transform

        df = pd.DataFrame(
            [
                {"outlet": "a.dk", "category": "Politics", "count": 30},
                {"outlet": "a.dk", "category": "Health", "count": 70},
                {"outlet": "b.dk", "category": "Politics", "count": 20},
                {"outlet": "b.dk", "category": "Health", "count": 20},
            ]
        )
        transformed, label = topics_metric_transform(df, "Share of Outlet Topics (%)")
        self.assertEqual(label, "Share (%)")
        self.assertAlmostEqual(
            float(transformed[(transformed["outlet"] == "a.dk") & (transformed["category"] == "Politics")]["value"].iloc[0]),
            30.0,
        )
        self.assertAlmostEqual(
            float(transformed[(transformed["outlet"] == "b.dk") & (transformed["category"] == "Politics")]["value"].iloc[0]),
            50.0,
        )

    def test_matrix_records_to_df_builds_symmetric_matrix(self):
        from pages.explorer import _matrix_records_to_df

        entities = ["denmark", "sweden", "norway"]
        records = [
            {"entity_a": "denmark", "entity_b": "sweden", "value": 0.8},
            {"entity_a": "denmark", "entity_b": "norway", "value": 0.6},
        ]
        matrix = _matrix_records_to_df(records, entities)
        self.assertEqual(matrix.loc["denmark", "denmark"], 1.0)
        self.assertEqual(matrix.loc["sweden", "denmark"], 0.8)
        self.assertEqual(matrix.loc["norway", "denmark"], 0.6)

    def test_similarity_helpers_mask_diagonal_and_scale_cross_country_values(self):
        from pages.explorer import _mask_matrix_diagonal, _similarity_color_bounds

        matrix = pd.DataFrame(
            [[1.0, 0.91, 0.96], [0.91, 1.0, 0.94], [0.96, 0.94, 1.0]],
            index=["Denmark", "Sweden", "Norway"],
            columns=["Denmark", "Sweden", "Norway"],
        )
        display_matrix = _mask_matrix_diagonal(matrix)
        self.assertTrue(pd.isna(display_matrix.loc["Denmark", "Denmark"]))
        self.assertEqual(display_matrix.loc["Denmark", "Norway"], 0.96)

        zmin, zmax = _similarity_color_bounds(display_matrix)
        self.assertLess(zmin, 0.91)
        self.assertGreater(zmax, 0.96)
        self.assertLessEqual(zmax, 1.0)

    def test_wrap_two_line_label(self):
        from pages.explorer import _wrap_two_line_label

        self.assertEqual(_wrap_two_line_label("Short"), "Short")
        self.assertEqual(
            _wrap_two_line_label("Politics & Governance"),
            "Politics &<br>Governance",
        )

    def test_filter_label_helpers(self):
        from pages.explorer import _partisan_label, _period_label

        self.assertEqual(_period_label(2016, 2026), "2016-2026")
        self.assertEqual(_partisan_label(None), "All orientations")
        self.assertEqual(_partisan_label("Right"), "Right")

    def test_plot_renders_scatter_and_heatmap_with_valid_plotly_properties(self):
        import plotly.graph_objects as go

        from pages.explorer import _plot

        figures = [
            go.Figure(data=[go.Scatter(x=[1, 2], y=[3, 4])], layout={"height": 430}),
            go.Figure(
                data=[go.Heatmap(z=[[1, 0.5], [0.5, 1]])],
                layout={"height": 640},
            ),
        ]
        with patch("pages.explorer.st.plotly_chart") as plotly_chart:
            for figure in figures:
                _plot(figure)

        self.assertEqual(plotly_chart.call_count, 2)
        self.assertEqual(figures[0].layout.height, 340)
        self.assertEqual(figures[1].layout.height, 390)

if __name__ == "__main__":
    unittest.main()
