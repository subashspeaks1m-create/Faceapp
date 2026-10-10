import json
import unittest

from styleapi.catalog import CATALOG_PATH, Catalog, build_prompt, load_catalog, public_catalog, public_catalog_json

EXPECTED = [
    ("retro", "70s Retro Film"),
    ("retro", "80s Neon"),
    ("retro", "90s Flash Photograph"),
    ("retro", "Vintage Polaroid"),
    ("illustration", "Ghibli-Inspired Storybook"),
    ("illustration", "3D Animated Character"),
    ("illustration", "Manga Ink"),
    ("illustration", "Comic Book"),
    ("illustration", "Watercolor Painting"),
    ("illustration", "Oil Painting"),
    ("illustration", "Pop Art"),
    ("illustration", "Pixel Art"),
    ("cinematic", "Cyberpunk"),
    ("cinematic", "Film Noir"),
    ("cinematic", "Cinematic Poster"),
    ("cinematic", "Fantasy Elf"),
    ("cinematic", "Dreamy Fairycore"),
    ("editorial", "Professional Headshot"),
    ("editorial", "Fashion Editorial"),
    ("editorial", "Wedding Glow"),
    ("editorial", "Streetwear Campaign"),
    ("artistic", "Renaissance Portrait"),
    ("artistic", "Clay Figure"),
    ("artistic", "Golden Hour"),
    ("artistic", "Fine-Art Monochrome"),
]


class CatalogTest(unittest.TestCase):
    def test_exact_25_styles_in_order(self) -> None:
        c = load_catalog()
        self.assertEqual([(s.category, s.name) for s in c.styles], EXPECTED)
        self.assertEqual([s.number for s in c.styles], list(range(1, 26)))

    def test_public_catalog_has_no_prompt_text(self) -> None:
        pub = public_catalog()
        text = json.dumps(pub)
        self.assertNotIn("prompt", text)
        for s in load_catalog().styles:
            self.assertNotIn(s.prompt.style[:40], text)
        self.assertEqual(set(pub["styles"][0]), {"id", "number", "name", "category", "summary", "tags", "default_intensity", "swatch"})  # type: ignore[index]

    def test_public_json_is_stable(self) -> None:
        self.assertEqual(public_catalog_json(), public_catalog_json())

    def test_bands_boundaries(self) -> None:
        c = load_catalog()
        for value, label in [(0, "Subtle"), (25, "Subtle"), (26, "Moderate"), (50, "Moderate"), (51, "Strong"), (75, "Strong"), (76, "Full"), (100, "Full")]:
            self.assertEqual(c.band(value).label, label, value)

    def test_prompt_structure(self) -> None:
        c = load_catalog()
        for s in c.styles:
            for intensity in (0, 30, 60, 90):
                p = build_prompt(s, intensity)
                self.assertIn("same individual", p)
                self.assertIn("Keep exactly the same number of people", p)
                self.assertIn("Do not add text", p)
                self.assertIn(s.prompt.style[:30], p)
                self.assertIn(f"Strength {intensity}/100", p)
                self.assertEqual(s.prompt.high_intensity in p, intensity >= 76)
                self.assertLess(len(p), 4000)

    def test_prompts_do_not_name_studios_or_characters(self) -> None:
        raw = CATALOG_PATH.read_text().lower()
        for banned in ("ghibli studio", "studio ghibli", "miyazaki", "totoro", "pixar", "disney", "marvel", "dc comics", "aardman"):
            self.assertNotIn(banned, raw)

    def test_out_of_range_intensity_rejected(self) -> None:
        s = load_catalog().styles[0]
        for bad in (-1, 101):
            with self.assertRaises(ValueError):
                build_prompt(s, bad)

    def test_rejects_unknown_fields_and_gaps(self) -> None:
        data = json.loads(CATALOG_PATH.read_text())
        data["styles"][0]["extra"] = 1
        with self.assertRaises(ValueError):
            Catalog.model_validate(data)
        data = json.loads(CATALOG_PATH.read_text())
        data["intensity_bands"][1]["min"] = 27
        with self.assertRaises(ValueError):
            Catalog.model_validate(data)
        data = json.loads(CATALOG_PATH.read_text())
        data["styles"][1]["id"] = data["styles"][0]["id"]
        with self.assertRaises(ValueError):
            Catalog.model_validate(data)


class GeneratedModuleTest(unittest.TestCase):
    def test_app_module_matches_catalog(self) -> None:
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "scripts" / "export_public_catalog.py"
        spec = importlib.util.spec_from_file_location("export_public_catalog", path)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.TARGET.read_text(), mod.render(), "run apps/style-api/scripts/export_public_catalog.py")


if __name__ == "__main__":
    unittest.main()
