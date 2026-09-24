from pathlib import Path
import unittest


class FilterControlStyleTests(unittest.TestCase):
    def test_segmented_and_dropdown_filters_have_explicit_contrast(self):
        app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text()

        self.assertIn('div[data-testid="stSegmentedControl"] button', app_source)
        self.assertIn('background-color: #ffffff !important;', app_source)
        self.assertIn('color: #243447 !important;', app_source)
        self.assertIn('ul[role="listbox"]', app_source)
        self.assertIn('aria-selected="true"', app_source)


if __name__ == "__main__":
    unittest.main()
