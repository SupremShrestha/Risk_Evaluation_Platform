import unittest
import pandas as pd
from build_features import build_full_grid


class BuildFullGridTests(unittest.TestCase):
    def test_grid_only_includes_real_observed_periods(self):
        """
        Regression test: the grid must NOT include (year, month) combinations
        that never appeared in the source data — even if other years in the
        dataset do have that month. This is what caused the original bug:
        2024 only has Jul-Dec, 2026 only has Jan-Jul, but a naive
        districts x hazards x years x months cross product invented fake
        Oct/Nov/Dec 2026 rows, corrupting both training and evaluation.
        """
        raw = pd.DataFrame([
            {"district": "Rolpa", "hazard": "Landslide", "year": 2024, "month": 7, "incident_count": 5},
            {"district": "Rolpa", "hazard": "Landslide", "year": 2024, "month": 8, "incident_count": 3},
            {"district": "Rolpa", "hazard": "Landslide", "year": 2026, "month": 1, "incident_count": 1},
        ])

        grid = build_full_grid(raw)
        observed_periods = set(zip(grid["year"], grid["month"]))

        # These real periods must be present
        self.assertIn((2024, 7), observed_periods)
        self.assertIn((2024, 8), observed_periods)
        self.assertIn((2026, 1), observed_periods)

        # These periods never existed in source data and must NOT appear
        self.assertNotIn((2024, 1), observed_periods)   # Jan 2024 never in data
        self.assertNotIn((2026, 12), observed_periods)  # Dec 2026 never in data

    def test_zero_fill_applies_to_missing_district_hazard_combos(self):
        """
        A district/hazard combo with no incidents in a real period should
        appear as count=0, not be silently dropped — the model needs to see
        'nothing happened here' as real information, not missing data.
        """
        raw = pd.DataFrame([
            {"district": "Rolpa", "hazard": "Landslide", "year": 2024, "month": 7, "incident_count": 5},
            {"district": "Kathmandu", "hazard": "Fire", "year": 2024, "month": 7, "incident_count": 2},
        ])

        grid = build_full_grid(raw)

        # Rolpa should have a Fire row for 2024-07, even though it had none
        rolpa_fire = grid[
            (grid["district"] == "Rolpa")
            & (grid["hazard"] == "Fire")
            & (grid["year"] == 2024)
            & (grid["month"] == 7)
        ]
        self.assertEqual(len(rolpa_fire), 1)
        self.assertEqual(rolpa_fire.iloc[0]["incident_count"], 0)


if __name__ == "__main__":
    unittest.main()