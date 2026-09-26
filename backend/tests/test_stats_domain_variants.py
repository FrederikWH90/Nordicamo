import unittest


class TestStatsDomainVariants(unittest.TestCase):
    def test_domain_variants(self):
        from app.services.stats_service import domain_variants

        self.assertEqual(set(domain_variants("document.no")), {"document.no", "www.document.no"})
        self.assertEqual(
            set(domain_variants("www.nyadagbladet.se")),
            {"nyadagbladet.se", "www.nyadagbladet.se"},
        )

    def test_canonical_domain(self):
        from app.services.stats_service import canonical_domain

        self.assertEqual(canonical_domain("WWW.Document.no"), "document.no")
        self.assertEqual(canonical_domain("document.no"), "document.no")


class _FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class _FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []
        self.params = []

    def execute(self, query, params=None):
        self.queries.append(str(query))
        self.params.append(params or {})
        return _FakeResult(self.rows)


class TestStatsDomainAggregation(unittest.TestCase):
    def test_outlet_profile_aggregates_domain_variants(self):
        from app.services.stats_service import StatsService

        db = _FakeDB(
            [("www.document.no", "Document", "norway", 105029, "2008-01-01", "2026-05-05")]
        )
        profile = StatsService(db).get_outlet_profile("www.document.no")

        self.assertEqual(profile["domain"], "www.document.no")
        self.assertEqual(profile["total_articles"], 105029)
        self.assertEqual(profile["last_article_date"], "2026-05-05")
        self.assertIn("LOWER(domain) = ANY(:domains)", db.queries[0])
        self.assertNotIn("GROUP BY LOWER(domain)", db.queries[0])
        self.assertEqual(set(db.params[0]["domains"]), {"document.no", "www.document.no"})

    def test_top_outlets_aggregates_domain_and_metadata_variants(self):
        from app.services.stats_service import StatsService

        db = _FakeDB([("www.document.no", "Document", "norway", "Right", 105029)])
        rows = StatsService(db).get_top_outlets(limit=1)

        self.assertEqual(rows[0]["domain"], "www.document.no")
        self.assertEqual(rows[0]["count"], 105029)
        self.assertIn("REGEXP_REPLACE(LOWER(domain)", db.queries[0])
        self.assertIn("'^www\\.'", db.queries[0])
        self.assertIn("GROUP BY domain_key", db.queries[0])

    def test_articles_over_time_by_outlet_groups_canonical_domain(self):
        from app.services.stats_service import StatsService

        db = _FakeDB([("2026-05", "document.no", 120)])
        rows = StatsService(db).get_articles_over_time_by_outlet(
            ["document.no"],
            country="norway",
            granularity="month",
        )

        self.assertEqual(rows[0]["outlet"], "document.no")
        self.assertIn("REGEXP_REPLACE(LOWER(domain)", db.queries[0])
        group_clause = db.queries[0].split("GROUP BY", 1)[1].split("ORDER BY")[0]
        self.assertIn("REGEXP_REPLACE(LOWER(domain)", group_clause)
        self.assertNotIn("LOWER(domain)", group_clause.replace("REGEXP_REPLACE(LOWER(domain)", ""))

    def test_outlet_concentration_merges_domain_variants(self):
        from app.services.stats_service import StatsService

        class _SequentialDB(_FakeDB):
            def __init__(self, rows_by_call):
                super().__init__([])
                self.rows_by_call = rows_by_call
                self.call = 0

            def execute(self, query, params=None):
                self.queries.append(str(query))
                self.params.append(params or {})
                rows = self.rows_by_call[self.call]
                self.call += 1
                return _FakeResult(rows)

        seq_db = _SequentialDB(
            [
                [(2500,)],
                [
                    ("www.document.no", "norway", 1050),
                    ("inyheter.no", "norway", 200),
                ],
            ]
        )
        result = StatsService(seq_db).get_outlet_concentration(country="norway")

        self.assertEqual(result["outlets"][0]["count"], 1050)
        self.assertIn("domain_key", seq_db.queries[1])
        self.assertIn("GROUP BY domain_key", seq_db.queries[1])


if __name__ == "__main__":
    unittest.main()
