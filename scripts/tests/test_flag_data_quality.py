import os
import re
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import flag_data_quality as dq  # noqa: E402


class TestTeaserTrim(unittest.TestCase):
    def test_document_no_teaser_keeps_the_lead(self):
        text = ("Forholdene ved Energigjenvinningsetaten skal granskes. Logg inn for å lese videre (abonnenter). "
                "Støtt Norges viktigste uavhengige medium! Bli abonnent")
        self.assertEqual(dq.strip_paywall_tail(text), "Forholdene ved Energigjenvinningsetaten skal granskes.")

    def test_samnytt_and_nyatider(self):
        self.assertEqual(
            dq.strip_paywall_tail("Vaccin stoppas Få tillgång till exklusivt material med Samnytt PLUS! mer"),
            "Vaccin stoppas",
        )
        self.assertEqual(dq.strip_paywall_tail("Ingress här. Artikeln fortsätter Är du prenumerant"), "Ingress här.")

    def test_no_phrase_or_no_lead(self):
        self.assertIsNone(dq.strip_paywall_tail("A normal full article."))
        self.assertIsNone(dq.strip_paywall_tail("Logg inn for å lese videre"))
        self.assertIsNone(dq.strip_paywall_tail(None))


class TestMojibake(unittest.TestCase):
    def test_repairs_and_reports_no_change(self):
        self.assertEqual(dq.repair_mojibake("SVT lÃ¦rer barn"), "SVT lærer barn")
        self.assertEqual(dq.repair_mojibake("valmetod â nÃ¤r klanen"), "valmetod – när klanen")
        self.assertIsNone(dq.repair_mojibake("Allerede korrekt: æøå"))
        self.assertIsNone(dq.repair_mojibake(None))


class TestIdempotency(unittest.TestCase):
    def test_near_empty_rule_skips_recorded_teasers(self):
        # Regression: trimmed teasers are short; a second run must not flag them as empty.
        sql = dq.CANDIDATES_SQL
        self.assertIn("LEFT JOIN article_content_status s ON s.article_id = b.id", sql)
        near_empty_clause = next(line for line in sql.splitlines() if "dq_near_empty" in line)
        self.assertIn("s.article_id IS NULL", near_empty_clause)

    def test_repeated_title_rule_spares_recurring_columns(self):
        self.assertIn("count(DISTINCT b.body_hash) <=", dq.CANDIDATES_SQL)


class TestNonArticle(unittest.TestCase):
    def test_listing_and_attachment_pages(self):
        for url in (
            "https://www.frihetskamp.no/tag/autisme/",
            "https://solidaritet.dk/tag/laerere/",
            "https://nyadagbladet.se/donera/attachment/btcpay/",
            "https://nyadagbladet.se/?attachment_id=108264",
            "https://example.dk/page/3/",
            "https://example.no/forfatter/ola/",
        ):
            self.assertTrue(dq.is_non_article(url, "x"), url)
        self.assertTrue(dq.is_non_article("https://x.no/a", "Stikkord: Herbert Kickl"))

    def test_real_articles_pass(self):
        for url in (
            "https://www.document.no/2020/09/06/frihetens-og-fornuftens-byrde/",
            "https://samnytt.se/tagen-pa-bar-gärning/",
            "https://example.se/kategorisk-vagran/",
        ):
            self.assertFalse(dq.is_non_article(url, "Ett riktigt reportage"), url)

    def test_patterns_are_postgres_compatible(self):
        # The same patterns are sent to Postgres (~*); keep them to syntax both engines share.
        for pattern in (dq.NON_ARTICLE_URL, dq.NON_ARTICLE_TITLE, dq.TEASER_CUT):
            self.assertNotRegex(pattern, r"\(\?[:=!<]")
            re.compile(pattern)


if __name__ == "__main__":
    unittest.main()
