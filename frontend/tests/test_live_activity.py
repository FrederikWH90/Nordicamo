import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from live_activity import (  # noqa: E402
    CountryActivity,
    activity_window_end,
    activity_window_start,
    display_domain,
    format_delta,
    nordic_totals,
    relative_day,
    repair_mojibake,
    select_latest_feed,
    sparkline_svg,
    summarise_country,
    weekly_blocks,
)

TODAY = date(2026, 9, 26)


def daily(start: date, days: int, count: int = 1):
    return [{"date": (start + timedelta(days=i)).isoformat(), "count": count} for i in range(days)]


class TestWeeklyBlocks(unittest.TestCase):
    def test_last_block_ends_before_days_still_being_collected(self):
        rows = daily(date(2026, 9, 18), 7, count=10)  # 18..24 Sep
        rows.append({"date": "2026-09-25", "count": 999})  # yesterday: still backfilling
        rows.append({"date": "2026-09-26", "count": 999})  # today: in progress
        rows.append({"date": "2026-09-17", "count": 5})  # previous block
        self.assertEqual(activity_window_end(TODAY), date(2026, 9, 24))
        self.assertEqual(weekly_blocks(rows, TODAY, weeks=2), [5, 70])

    def test_lag_can_be_disabled(self):
        rows = daily(date(2026, 9, 20), 7, count=1)  # 20..26 Sep
        self.assertEqual(weekly_blocks(rows, TODAY, weeks=1, lag_days=0), [7])

    def test_window_start_covers_all_blocks(self):
        start = activity_window_start(TODAY, weeks=13)
        rows = daily(start, 91, count=1)
        self.assertEqual(weekly_blocks(rows, TODAY, weeks=13), [7] * 13)

    def test_bad_rows_are_skipped(self):
        rows = [{"date": None, "count": 3}, {"date": "2026-09-24", "count": "x"}, {"date": "2026-09-24", "count": 2}]
        self.assertEqual(weekly_blocks(rows, TODAY, weeks=1), [2])


class TestSummaries(unittest.TestCase):
    def test_summary_headline_matches_last_sparkline_point(self):
        rows = daily(activity_window_start(TODAY), 91, count=2)
        summary = summarise_country("denmark", rows, TODAY, active_outlets=12)
        self.assertEqual(summary.last_7_days, summary.weekly_series[-1])
        self.assertEqual(summary.previous_7_days, 14)
        self.assertEqual(summary.delta_ratio, 0)

    def test_delta_is_none_without_previous_week(self):
        self.assertIsNone(CountryActivity("x", 10, 0).delta_ratio)

    def test_format_delta(self):
        self.assertEqual(format_delta(0.123), ("▲ 12% vs previous 7 days", "up"))
        self.assertEqual(format_delta(-0.5), ("▼ 50% vs previous 7 days", "down"))
        self.assertEqual(format_delta(0.001)[1], "flat")
        self.assertEqual(format_delta(None)[1], "flat")

    def test_nordic_totals_sum_countries(self):
        a = CountryActivity("denmark", 10, 5, [1, 2], 3)
        b = CountryActivity("sweden", 20, 15, [3, 4], 4)
        total = nordic_totals([a, b])
        self.assertEqual((total.last_7_days, total.previous_7_days, total.active_outlets), (30, 20, 7))
        self.assertEqual(total.weekly_series, [4, 6])


class TestFormatting(unittest.TestCase):
    def test_relative_day(self):
        self.assertEqual(relative_day("2026-09-26", TODAY), "Today")
        self.assertEqual(relative_day("2026-09-25T10:00:00", TODAY), "Yesterday")
        self.assertEqual(relative_day("2026-09-22", TODAY), "4 days ago")
        self.assertEqual(relative_day("2026-08-01", TODAY), "1 Aug 2026")
        self.assertEqual(relative_day(None, TODAY), "")

    def test_display_domain_strips_www(self):
        self.assertEqual(display_domain("WWW.Document.dk"), "document.dk")
        self.assertEqual(display_domain(None), "")

    def test_sparkline_is_escaped_svg(self):
        svg = sparkline_svg([1, 5, 3], "#8c342f")
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("aria-label", svg)
        self.assertEqual(sparkline_svg([], "#000"), "")
        self.assertNotIn("<script", sparkline_svg([1, 2], "'><script>"))

    def test_sparkline_handles_all_zero(self):
        self.assertIn("polyline", sparkline_svg([0, 0, 0], "#000"))


class TestMojibake(unittest.TestCase):
    def test_repairs_double_encoded_nordic_characters(self):
        self.assertEqual(repair_mojibake("nÃ¤r klanen Ã¶vertrumfar"), "när klanen övertrumfar")
        self.assertEqual(repair_mojibake("Ã¦Ã¸Ã¥"), "æøå")

    def test_repairs_titles_with_lost_bytes(self):
        garbled = "S-profilens valmetod â nÃ¤r klanen Ã¶vertrumfar individen"
        self.assertEqual(repair_mojibake(garbled), "S-profilens valmetod – när klanen övertrumfar individen")

    def test_leaves_correct_text_alone(self):
        for text in ("när", "Kärnkraft", "plain ascii", "Årets Ãbo"):
            self.assertEqual(repair_mojibake(text), text)
        self.assertEqual(repair_mojibake(None), "")


class TestFeed(unittest.TestCase):
    def test_feed_keeps_newest_article_per_outlet(self):
        articles = [
            {"domain": "www.a.dk", "title": "A old", "date": "2026-09-20"},
            {"domain": "a.dk", "title": "A new", "date": "2026-09-25"},
            {"domain": "b.se", "title": "B", "date": "2026-09-24"},
            {"domain": "c.no", "title": "", "date": "2026-09-26"},
        ]
        feed = select_latest_feed(articles, limit=5)
        self.assertEqual([a["title"] for a in feed], ["A new", "B"])

    def test_feed_interleaves_outlets_when_taking_several_each(self):
        articles = [
            {"domain": "a.dk", "title": "A1", "date": "2026-09-25"},
            {"domain": "a.dk", "title": "A2", "date": "2026-09-24"},
            {"domain": "a.dk", "title": "A3", "date": "2026-09-23"},
            {"domain": "b.se", "title": "B1", "date": "2026-09-22"},
            {"domain": "b.se", "title": "B2", "date": "2026-09-21"},
        ]
        feed = select_latest_feed(articles, limit=10, per_outlet=2)
        self.assertEqual([a["title"] for a in feed], ["A1", "B1", "A2", "B2"])

    def test_feed_respects_limit(self):
        articles = [{"domain": f"{i}.dk", "title": "t", "date": "2026-09-25"} for i in range(20)]
        self.assertEqual(len(select_latest_feed(articles, limit=8)), 8)


if __name__ == "__main__":
    unittest.main()
