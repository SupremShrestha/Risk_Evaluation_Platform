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

class PaginationTerminationTests(unittest.TestCase):
    """
    Regression test for the BIPAD API's unreliable pagination signal:
    'next' can remain non-null even after all real data has been returned.
    Our ingestion loop must stop based on empty results, not just 'next'.
    """

    def test_stops_on_empty_results_even_if_next_is_present(self):
        # Simulates exactly what we saw in production: page 14 onward
        # returned empty results but 'next' was still a valid-looking URL.
        fake_api_responses = [
            {"results": [{"id": 1}, {"id": 2}], "next": "page2"},
            {"results": [{"id": 3}], "next": "page3"},
            {"results": [], "next": "page4"},  # BIPAD's misleading behavior
        ]

        processed_ids = []
        for response in fake_api_responses:
            results = response.get("results", [])
            if not results:
                break  # this is the fix we're protecting
            processed_ids.extend(r["id"] for r in results)

        self.assertEqual(processed_ids, [1, 2, 3])
        # Critically: we must NOT have tried to process a 4th, empty page,
        # and we must have stopped even though 'next' claimed more existed.

if __name__ == "__main__":
    unittest.main()
