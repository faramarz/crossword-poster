"""Smoke tests. Run from the repo root:  python -m unittest discover -s tests -v   (or: pytest tests)

The pool / generate / validate tests need only the standard library. The render test is skipped automatically when
Playwright, PyMuPDF or a Chromium executable are not available."""
import csv
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
SAMPLE = os.path.join(ROOT, "examples", "sample_clues.csv")

from crossword_poster import generate as gen, pool as poolmod, validate as val  # noqa: E402


class PoolAndGrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.rows, cls.report = poolmod.build_pool(SAMPLE)
        b, stats = gen.generate_all([r["grid"] for r in cls.rows], attempts=200, seed=1, workers=1)
        assert b is not None, "no complete layout for the sample"
        cls.stats = stats
        cls.res = gen.attach_pool(gen.to_result(b, [], stats), cls.rows)
        gen.write_grid_files(cls.res, cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_pool_normalises(self):
        self.assertEqual(poolmod.grid_word("Mount Saint-Hélène"), "MOUNTSAINTHELENE")
        self.assertEqual(poolmod.enumeration("Big Ben"), "(3,3)")
        self.assertEqual(len(self.rows), 56)
        self.assertEqual(self.report["skipped"], [])
        self.assertEqual(self.report["giveaways"], [])
        big = next(r for r in self.rows if r["grid"] == "BIGBEN")
        self.assertTrue(big["clue"].endswith("(3,3)"))

    def test_all_answers_placed_and_valid(self):
        self.assertEqual(self.stats["words_placed"], len(self.rows))
        errs, _ = val.validate(os.path.join(self.tmp, "grid.json"), pool=self.rows)
        self.assertEqual(errs, [])

    def test_deterministic_for_a_seed(self):
        b2, _ = gen.generate_all([r["grid"] for r in self.rows], attempts=200, seed=1, workers=1)
        r2 = gen.to_result(b2, [], {})
        self.assertEqual(r2["grid"], self.res["grid"])

    def test_validator_catches_a_broken_grid(self):
        bad = json.loads(json.dumps(self.res))
        r, c = next((r, c) for r, row in enumerate(bad["grid"]) for c, ch in enumerate(row) if ch)
        bad["grid"][r][c] = "#" if bad["grid"][r][c] != "#" else "A"
        p = os.path.join(self.tmp, "bad.json")
        with open(p, "w") as f:
            json.dump(bad, f)
        errs, _ = val.validate(p)
        self.assertTrue(errs)


def _render_available():
    try:
        import pymupdf  # noqa: F401
        from playwright.sync_api import sync_playwright
        from crossword_poster.common import launch
        with sync_playwright() as pw:
            launch(pw).close()
        return True
    except Exception:
        return False


@unittest.skipUnless(_render_available(), "Playwright + Chromium + PyMuPDF not available")
class EndToEnd(unittest.TestCase):
    def test_build_18x24_black(self):
        import pymupdf
        from crossword_poster.cli import main
        out = tempfile.mkdtemp()
        try:
            rc = main(["build", "--clues", SAMPLE, "--size", "18x24", "--style", "black", "--out", out,
                       "--attempts", "200", "--workers", "1", "--no-crops", "--title", "Smoke Test"])
            self.assertEqual(rc, 0)
            w, h = (lambda d: (d.rect.width / 72, d.rect.height / 72))(pymupdf.open(f"{out}/18x24/A_black/poster.pdf")[0])
            self.assertAlmostEqual(w, 18.25, delta=0.01)
            self.assertAlmostEqual(h, 24.25, delta=0.01)
            t = pymupdf.open(f"{out}/18x24/A_black/poster_trim.pdf")[0]
            self.assertAlmostEqual(t.rect.width / 72, 18.0, delta=0.01)
            self.assertTrue(os.path.getsize(f"{out}/18x24/A_black/poster.png") > 10000)
            for f in ("18x24/key.pdf", "18x24/actual_size_check_letter.pdf", "solution_letter.pdf"):
                self.assertTrue(os.path.exists(f"{out}/{f}"), f)
        finally:
            shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
