import unittest

from backend.app.duplicate_detection import Candidate, DuplicateDetector
from backend.app.text_normalization import normalize_ticket_text


def ticket(identifier, description, *, category="Plumbing", block="A", room="204", status="Open"):
    return Candidate(identifier, category, block, room, description, status)


class DuplicateDetectionTests(unittest.TestCase):
    def setUp(self):
        self.detector = DuplicateDetector(threshold=0.48, embeddings_enabled=False)

    def test_normalizes_common_hinglish_variations(self):
        normalized = normalize_ticket_text("Washroom ke basin ke neeche paani tapak raha hai!")
        self.assertIn("bathroom", normalized)
        self.assertIn("sink", normalized)
        self.assertIn("water", normalized)
        self.assertIn("leak", normalized)

    def test_equivalent_english_reports_match(self):
        source = ticket("NEW", "Water is leaking under the bathroom sink.")
        matches, method = self.detector.suggest(source, [ticket("FF-1", "Water leak below bathroom sink.")], exclude_id="NEW")
        self.assertEqual(method, "lexical_fallback")
        self.assertEqual(matches[0]["ticket_id"], "FF-1")

    def test_hinglish_and_english_reports_match(self):
        source = ticket("NEW", "Sink ke niche se water leak ho raha hai.")
        matches, _ = self.detector.suggest(source, [ticket("FF-2", "Water is leaking under the bathroom sink.")], exclude_id="NEW")
        self.assertEqual(matches[0]["ticket_id"], "FF-2")

    def test_unrelated_or_different_category_reports_do_not_match(self):
        source = ticket("NEW", "Water is leaking under sink.")
        candidates = [ticket("FF-3", "Wi-Fi not working in room.", category="Internet"), ticket("FF-4", "Bathroom mirror is broken.")]
        matches, _ = self.detector.suggest(source, candidates, exclude_id="NEW")
        self.assertEqual(matches, [])

    def test_resolved_and_current_ticket_excluded(self):
        source = ticket("NEW", "Water leaking under sink.")
        candidates = [ticket("NEW", "Water leaking under sink."), ticket("FF-5", "Water leaking under sink.", status="Resolved")]
        matches, _ = self.detector.suggest(source, candidates, exclude_id="NEW")
        self.assertEqual(matches, [])

    def test_category_block_and_location_raise_score(self):
        source = ticket("NEW", "Water leak under sink.", block="A", room="204")
        same_context = ticket("FF-6", "Water leaking below sink.", block="A", room="204")
        other_block = ticket("FF-7", "Water leaking below sink.", block="C", room="204")
        matches, _ = self.detector.suggest(source, [other_block, same_context], exclude_id="NEW")
        self.assertEqual(matches[0]["ticket_id"], "FF-6")

    def test_empty_or_malformed_input_uses_safe_empty_result(self):
        bad = Candidate("NEW", "Plumbing", "A", "204", None, "Open")
        matches, method = self.detector.suggest(bad, [ticket("FF-8", "Water leak")], exclude_id="NEW")
        self.assertEqual(matches, [])
        self.assertEqual(method, "lexical_fallback")


if __name__ == "__main__":
    unittest.main()
