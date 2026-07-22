import unittest
from ingest import extract_loss_id, extract_hazard_id


class ExtractLossIdTests(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(extract_loss_id(None))

    def test_plain_int_returned_as_is(self):
        self.assertEqual(extract_loss_id(464323), 464323)

    def test_nested_dict_extracts_id(self):
        self.assertEqual(extract_loss_id({"id": 464323, "deaths": 0}), 464323)

    def test_dict_without_id_returns_none(self):
        self.assertIsNone(extract_loss_id({"deaths": 0}))


class ExtractHazardIdTests(unittest.TestCase):
    def test_plain_int_returned_as_is(self):
        self.assertEqual(extract_hazard_id(17), 17)

    def test_nested_dict_extracts_id(self):
        self.assertEqual(extract_hazard_id({"id": 17, "title": "Landslide"}), 17)


if __name__ == "__main__":
    unittest.main()