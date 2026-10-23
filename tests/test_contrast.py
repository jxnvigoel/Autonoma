import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from engine.designer import calculate_contrast
from engine.judge import compute_contrast_ratio


class TestWCAGContrastValidator(unittest.TestCase):
    """
    Unit tests for WCAG 2.x standard contrast calculation.
    Reference values specified by standard WCAG 2.x sRGB linearization formula:
    - #000000 on #ffffff = 21.0
    - #767676 on #ffffff = 4.54
    - #777777 on #ffffff = 4.48
    - #0f172a on #f8fafc = 17.06
    - #38bdf8 on #0f172a = 8.33
    - #a0aec0 on #ffffff = 2.26
    - #718096 on #1a202c = 4.06
    """
    REFERENCE_PAIRS = [
        ("#000000", "#ffffff", 21.0),
        ("#767676", "#ffffff", 4.54),
        ("#777777", "#ffffff", 4.48),
        ("#0f172a", "#f8fafc", 17.06),
        ("#38bdf8", "#0f172a", 8.33),
        ("#a0aec0", "#ffffff", 2.26),
        ("#718096", "#1a202c", 4.06),
    ]

    def test_designer_contrast_reference_values(self):
        print("\n--- Testing engine/designer.py calculate_contrast ---")
        for fg, bg, expected in self.REFERENCE_PAIRS:
            ratio = calculate_contrast(fg, bg)
            rounded = round(ratio, 2)
            print(f"Designer: {fg} on {bg} -> {ratio:.4f} (rounded: {rounded:.2f}), expected: {expected}")
            self.assertEqual(
                rounded,
                expected,
                f"Designer contrast for {fg} on {bg} was {rounded}, expected {expected}"
            )

    def test_judge_contrast_reference_values(self):
        print("\n--- Testing engine/judge.py compute_contrast_ratio ---")
        for fg, bg, expected in self.REFERENCE_PAIRS:
            ratio = compute_contrast_ratio(fg, bg)
            rounded = round(ratio, 2)
            print(f"Judge:    {fg} on {bg} -> {ratio:.4f} (rounded: {rounded:.2f}), expected: {expected}")
            self.assertEqual(
                rounded,
                expected,
                f"Judge contrast for {fg} on {bg} was {rounded}, expected {expected}"
            )

    def test_contrast_symmetry(self):
        """Ratio must be identical regardless of foreground/background order."""
        for fg, bg, _ in self.REFERENCE_PAIRS:
            r1 = calculate_contrast(fg, bg)
            r2 = calculate_contrast(bg, fg)
            self.assertAlmostEqual(r1, r2, places=4)


if __name__ == "__main__":
    unittest.main()
