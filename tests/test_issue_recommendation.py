import unittest

from backend.app.issue_recommendation import IssueRecommender


class MissingEmbeddings:
    def embedding_for(self, _):
        return None


class IssueRecommendationTests(unittest.TestCase):
    def setUp(self):
        self.recommender = IssueRecommender(MissingEmbeddings())

    def test_english_plumbing_recommendation(self):
        recommendation = self.recommender.recommend("Water is leaking from the bathroom sink pipe.", "Plumbing")
        self.assertEqual(recommendation["category"]["recommended_category"], "Plumbing")
        self.assertEqual(recommendation["category"]["method"], "keyword_rules")
        self.assertEqual(recommendation["priority"]["recommended_priority"], "Medium")

    def test_hinglish_plumbing_recommendation(self):
        recommendation = self.recommender.recommend("Washroom ke basin ke neeche paani tapak raha hai.", "Other")
        self.assertEqual(recommendation["category"]["recommended_category"], "Plumbing")
        self.assertTrue(recommendation["category"]["differs_from_selected"])

    def test_hindi_electricity_recommendation(self):
        recommendation = self.recommender.recommend("कमरे की लाइट और स्विच काम नहीं कर रहे हैं।", "Other")
        self.assertEqual(recommendation["category"]["recommended_category"], "Electricity")
        self.assertEqual(recommendation["priority"]["recommended_priority"], "Medium")

    def test_ambiguous_text_keeps_selected_category(self):
        recommendation = self.recommender.recommend("Please inspect this issue.", "Furniture")
        self.assertEqual(recommendation["category"]["recommended_category"], "Furniture")
        self.assertEqual(recommendation["category"]["method"], "selected_category_fallback")

    def test_unknown_selection_and_text_fall_back_to_other(self):
        recommendation = self.recommender.recommend("Please inspect this issue.", "Unknown")
        self.assertEqual(recommendation["category"]["recommended_category"], "Other")
        self.assertEqual(recommendation["category"]["method"], "unknown_fallback")

    def test_safety_rules_override_context_in_english_and_hindi(self):
        english = self.recommender.recommend("There is sparking from the socket.", "Electricity")
        hindi = self.recommender.recommend("कमरे में आग और धुआँ है।", "Other")
        self.assertEqual(english["priority"]["recommended_priority"], "High")
        self.assertEqual(english["priority"]["method"], "safety_rule")
        self.assertEqual(hindi["priority"]["recommended_priority"], "High")

    def test_unavailable_embeddings_keep_rule_baseline(self):
        recommendation = self.recommender.recommend("Wi-Fi internet network is down.", "Internet")
        self.assertEqual(recommendation["category"]["method"], "keyword_rules")
        self.assertEqual(recommendation["category"]["recommended_category"], "Internet")


if __name__ == "__main__":
    unittest.main()
