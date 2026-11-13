"""V14.7: table cells are shortened (full text in the tooltip) and the gap text is compact."""
import unittest


def f_cut(s, n):
    """Mirror of Pine f_cut: keep n characters including the trailing ellipsis."""
    return s[: n - 1] + "…" if len(s) > n else s


def gap_txt(direction, pts, pct, filled, fill_pct, short):
    return ("UP " if direction == 1 else "DOWN ") + f"{pts} ({pct}%) " + ("FILLED" if filled else f"{fill_pct}% filled") + " | " + short


class TestTableText(unittest.TestCase):
    def test_cut_never_exceeds_limit(self):
        for n in (12, 34, 68):
            for s in ("x" * 5, "y" * n, "z" * (n + 1), "w" * 300):
                self.assertLessEqual(len(f_cut(s, n)), n)

    def test_short_text_is_untouched(self):
        self.assertEqual(f_cut("HOLD", 34), "HOLD")

    def test_gap_text_fits_default_cell(self):
        t = gap_txt(-1, "12.45", 18, False, 40, "fade to 2650.10")
        self.assertLessEqual(len(t), 48)
        self.assertLessEqual(len(f_cut(t, 34)), 34)


if __name__ == "__main__":
    unittest.main(verbosity=2)
