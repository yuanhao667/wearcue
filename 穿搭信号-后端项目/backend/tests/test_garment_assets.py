import unittest
from pathlib import Path
from xml.etree import ElementTree


GARMENT_ROOT = Path(__file__).resolve().parents[1] / "app" / "static" / "garments"


class GarmentAssetTests(unittest.TestCase):
    def test_final_runtime_library(self) -> None:
        expected = {"mens": 17, "womens": 20, "accessories": 5}
        actual = {
            collection: len(list((GARMENT_ROOT / collection).glob("*.svg")))
            for collection in expected
        }
        self.assertEqual(actual, expected)
        self.assertFalse(list(GARMENT_ROOT.glob("basic/*.svg")))

    def test_svg_files_are_valid_and_png_free(self) -> None:
        self.assertFalse(list(GARMENT_ROOT.rglob("*.png")))
        for path in GARMENT_ROOT.rglob("*.svg"):
            root = ElementTree.parse(path).getroot()
            self.assertEqual(root.attrib.get("viewBox"), "0 0 96 96", path.name)
            self.assertTrue(
                any(element.attrib.get("fill") == "currentColor" for element in root.iter()),
                "%s must contain a filled currentColor silhouette" % path.name,
            )


if __name__ == "__main__":
    unittest.main()
