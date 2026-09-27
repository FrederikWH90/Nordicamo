import unittest

from fastapi.testclient import TestClient


class TestOutletHelpers(unittest.TestCase):
    def test_clean_value_treats_imported_blanks_as_missing(self):
        from app.services.outlets_service import clean_value

        for blank in (None, "", "  ", "NaN", "nan", "None", "N/A"):
            self.assertIsNone(clean_value(blank), blank)
        self.assertEqual(clean_value("  Document "), "Document")

    def test_canonical_outlet(self):
        from app.services.outlets_service import canonical_outlet

        self.assertEqual(canonical_outlet("https://www.Document.no/"), "document.no")
        self.assertEqual(canonical_outlet("arbejderen.dk"), "arbejderen.dk")
        self.assertEqual(canonical_outlet(None), "")

    def test_safe_link_only_allows_web_links(self):
        from app.services.outlets_service import safe_link

        self.assertEqual(safe_link("https://twitter.com/arbejderen"), "https://twitter.com/arbejderen")
        self.assertEqual(safe_link("arbejderen.dk"), "https://arbejderen.dk")
        self.assertIsNone(safe_link("NaN"))
        self.assertIsNone(safe_link("javascript:alert(1)"))
        self.assertIsNone(safe_link("@handle"))

    def test_cosine(self):
        from app.services.outlets_service import cosine

        self.assertAlmostEqual(cosine({"a": 1.0}, {"a": 2.0}), 1.0)
        self.assertAlmostEqual(cosine({"a": 1.0}, {"b": 1.0}), 0.0)
        self.assertEqual(cosine({}, {"a": 1.0}), 0.0)


class TestSimilarity(unittest.TestCase):
    def test_centring_removes_the_shared_baseline(self):
        from app.services.outlets_service import centred_profiles, cosine

        vectors = {
            "left1": {"Politics": 0.9, "Climate": 0.4, "Crime": 0.05},
            "left2": {"Politics": 0.9, "Climate": 0.35, "Crime": 0.05},
            "right1": {"Politics": 0.9, "Climate": 0.05, "Crime": 0.4},
        }
        raw = cosine(vectors["left1"], vectors["right1"])
        self.assertGreater(raw, 0.8)  # the problem: everything looks similar
        c = centred_profiles(vectors, {k: 100 for k in vectors})
        self.assertGreater(cosine(c["left1"], c["left2"]), 0.9)
        self.assertLess(cosine(c["left1"], c["right1"]), 0)

    def test_shared_emphasis_names_topics_both_cover_above_average(self):
        from app.services.outlets_service import shared_emphasis

        self.assertEqual(shared_emphasis({"Climate": 0.2, "Crime": -0.1}, {"Climate": 0.15, "Crime": 0.3}), ["Climate"])
        self.assertEqual(shared_emphasis({"A": -0.1}, {"A": -0.2}), [])


class DummyOutletsService:
    def __init__(self, db):
        pass

    def directory(self):
        return {"months": ["2026-08"], "outlets": [{"outlet": "a.dk", "articles": 3}]}

    def profile(self, outlet, latest=10, similar=6):
        return None if outlet == "missing.dk" else {"outlet": outlet, "latest_limit": latest}


class TestOutletRoutes(unittest.TestCase):
    def setUp(self):
        from app.main import app
        from app.api import outlets as outlets_module
        from app.database import get_db

        self.app, self.module = app, outlets_module
        self.original = outlets_module.OutletsService
        outlets_module.OutletsService = DummyOutletsService
        self.app.dependency_overrides[get_db] = lambda: None
        self.client = TestClient(self.app)

    def tearDown(self):
        self.module.OutletsService = self.original
        self.app.dependency_overrides.clear()

    def test_directory(self):
        response = self.client.get("/api/outlets")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["outlets"][0]["outlet"], "a.dk")

    def test_profile_with_dotted_domain_and_404(self):
        self.assertEqual(self.client.get("/api/outlets/document.no?latest=5").json()["latest_limit"], 5)
        self.assertEqual(self.client.get("/api/outlets/missing.dk").status_code, 404)
        self.assertEqual(self.client.get("/api/outlets/a.dk?latest=500").status_code, 422)
