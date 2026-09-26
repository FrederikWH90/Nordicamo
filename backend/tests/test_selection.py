import unittest

from fastapi.testclient import TestClient


class TestBuildTsquery(unittest.TestCase):
    def test_words_prefix_phrase_or_exclude(self):
        from app.services.selection_service import build_tsquery

        self.assertEqual(build_tsquery("klimat"), "klimat")
        self.assertEqual(build_tsquery("Klimat*"), "klimat:*")
        self.assertEqual(build_tsquery('"grønne omstilling"'), "(grønne <-> omstilling)")
        self.assertEqual(build_tsquery("covid OR corona"), "(covid | corona)")
        self.assertEqual(build_tsquery("ukraine -russia"), "ukraine & !russia")
        self.assertEqual(build_tsquery("covid-19"), "(covid <-> 19)")
        self.assertEqual(build_tsquery("vaccin* OR covid migration"), "(vaccin:* | covid) & migration")

    def test_empty_and_operator_only_input(self):
        from app.services.selection_service import build_tsquery

        for value in (None, "", "   ", "OR", '""', "-", "!!! &&& |||"):
            self.assertIsNone(build_tsquery(value), value)

    def test_input_cannot_inject_operators(self):
        from app.services.selection_service import build_tsquery

        # Raw tsquery operators and quotes in user input are stripped; only our own syntax survives.
        self.assertEqual(build_tsquery("a:* & (b | !c) <-> d')"), "a:* & b & c & d")
        self.assertEqual(build_tsquery("x'); DROP TABLE articles; --"), "x & (drop) & table & articles".replace("(drop)", "drop"))

    def test_leading_or_is_ignored(self):
        from app.services.selection_service import build_tsquery

        self.assertEqual(build_tsquery("OR migration"), "migration")


class DummySelectionService:
    calls = []

    def __init__(self, db):
        self.db = db

    def describe(self, **kwargs):
        DummySelectionService.calls.append(kwargs)
        return {"total": 3, "sample": [], "by_country": [], "by_outlet": [], "by_month": [], "by_topic": []}


class TestSelectionEndpoint(unittest.TestCase):
    def setUp(self):
        from app.main import app
        from app.api import articles as articles_module
        from app.database import get_db

        self.app = app
        self.module = articles_module
        self.original = articles_module.SelectionService
        articles_module.SelectionService = DummySelectionService
        DummySelectionService.calls = []
        self.app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(self.app)

    def tearDown(self):
        self.module.SelectionService = self.original
        self.app.dependency_overrides.clear()

    def test_repeated_list_params_keep_commas_inside_topic_names(self):
        response = self.client.get(
            "/api/articles/selection",
            params=[("countries", "sweden"), ("countries", "norway"),
                    ("topics", "Environment, Climate & Energy"), ("q", "klimat*"), ("order", "newest")],
        )
        self.assertEqual(response.status_code, 200)
        call = DummySelectionService.calls[0]
        self.assertEqual(call["countries"], ["sweden", "norway"])
        self.assertEqual(call["topics"], ["Environment, Climate & Energy"])
        self.assertEqual(call["order"], "newest")

    def test_rejects_oversized_sample_and_bad_order(self):
        self.assertEqual(self.client.get("/api/articles/selection", params={"sample_size": 5000}).status_code, 422)
        self.assertEqual(self.client.get("/api/articles/selection", params={"order": "drop"}).status_code, 422)

    def test_response_never_contains_article_text(self):
        from app.services import selection_service

        source = selection_service.__file__
        text = open(source, encoding="utf-8").read()
        sample_block = text[text.index("sample AS ("):text.index("SELECT totals.n")]
        self.assertNotIn("'content'", sample_block)
        self.assertNotIn("content_clean", sample_block)


if __name__ == "__main__":
    unittest.main()
