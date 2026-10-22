"""Explainable category and urgency recommendations for maintenance reports.

This is a curated keyword-profile baseline, not a trained classifier. It works
offline for English, Devanagari Hindi, and common Hinglish terms. When the
optional Part 1 embedding model is available, it only adds profile similarity;
critical safety decisions always remain deterministic rules.
"""

from __future__ import annotations

import math
from typing import Protocol

from backend.app.text_normalization import normalize_ticket_text


CATEGORIES = ("Plumbing", "Electricity", "Lift", "Cleaning", "Security", "Internet", "Furniture", "Other")

# These are maintenance vocabulary profiles, manually maintained for a local
# demo. They are not labelled training data and must not be reported as one.
CATEGORY_TERMS = {
    "Plumbing": ("water", "leak", "pipe", "drain", "sink", "tap", "toilet", "flush", "sewage", "पानी", "रिसाव", "नल", "पाइप", "सिंक", "बाथरूम"),
    "Electricity": ("electricity", "power", "light", "bulb", "tube", "switch", "socket", "wire", "current", "shock", "sparking", "बिजली", "लाइट", "बल्ब", "स्विच", "करंट", "तार"),
    "Lift": ("elevator", "stuck", "floor", "elevator door", "लिफ्ट", "फंसा"),
    "Cleaning": ("cleaning", "dirty", "garbage", "waste", "smell", "clean", "dust", "सफाई", "कचरा", "गंदा", "बदबू"),
    "Security": ("security", "lock", "key", "theft", "stolen", "intruder", "unsafe", "सुरक्षा", "ताला", "चाबी", "चोरी", "खतरा"),
    "Internet": ("wifi", "wi fi", "internet", "network", "router", "connection", "वाईफाई", "इंटरनेट", "नेटवर्क"),
    "Furniture": ("bed", "chair", "table", "desk", "mattress", "wardrobe", "cupboard", "furniture", "बिस्तर", "कुर्सी", "मेज", "अलमारी"),
    "Other": (),
}

SAFETY_INDICATORS = (
    ("fire", "fire reported"),
    ("smoke", "smoke reported"),
    ("gas leak", "gas leak reported"),
    ("electric shock", "electric shock reported"),
    ("live wire", "live wire reported"),
    ("sparking", "sparking reported"),
    ("flood", "flooding reported"),
    ("stuck", "person or equipment stuck reported"),
    ("immediate danger", "immediate danger reported"),
    ("elevator stuck", "elevator stuck reported"),
    ("stuck in elevator", "person stuck in elevator reported"),
    ("आग", "fire reported"),
    ("धुआँ", "smoke reported"),
    ("गैस रिसाव", "gas leak reported"),
    ("करंट", "electric shock/current reported"),
    ("चिंगारी", "sparking reported"),
    ("तुरंत खतरा", "immediate danger reported"),
)


class EmbeddingProvider(Protocol):
    def embedding_for(self, value: object) -> list[float] | None: ...


def _contains(text: str, phrase: str) -> bool:
    return phrase in text if " " in phrase else phrase in text.split()


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_size = math.sqrt(sum(value * value for value in left))
    right_size = math.sqrt(sum(value * value for value in right))
    return numerator / (left_size * right_size) if left_size and right_size else 0.0


class IssueRecommender:
    """Return explainable advice; never decides workflow or user permissions."""

    def __init__(self, embedding_provider: EmbeddingProvider | None = None):
        self.embedding_provider = embedding_provider
        self._profile_embeddings: dict[str, list[float]] = {}

    def _embedding_scores(self, normalized_text: str) -> dict[str, float]:
        if not self.embedding_provider:
            return {}
        source = self.embedding_provider.embedding_for(normalized_text)
        if source is None:
            return {}
        scores = {}
        for category, terms in CATEGORY_TERMS.items():
            if not terms:
                continue
            profile = self._profile_embeddings.get(category)
            if profile is None:
                profile = self.embedding_provider.embedding_for(" ".join(terms))
                if profile is not None:
                    self._profile_embeddings[category] = profile
            if profile is not None:
                scores[category] = _cosine(source, profile)
        return scores

    def recommend_category(self, description: object, selected_category: str | None = None) -> dict:
        text = normalize_ticket_text(description)
        selected = selected_category if selected_category in CATEGORIES else None
        keyword_hits = {category: [term for term in terms if _contains(text, term)] for category, terms in CATEGORY_TERMS.items() if terms}
        keyword_scores = {category: len(hits) for category, hits in keyword_hits.items()}
        top_keyword = max(keyword_scores, key=keyword_scores.get, default="Other")
        hit_count = keyword_scores.get(top_keyword, 0)
        embedding_scores = self._embedding_scores(text) if text else {}
        top_embedding = max(embedding_scores, key=embedding_scores.get, default="Other")

        if hit_count >= 2:
            recommended = top_keyword
            confidence = min(0.9, 0.52 + (hit_count * 0.12))
            method = "keyword_rules"
            reason = f"Matched: {', '.join(keyword_hits[top_keyword][:3])}."
        elif embedding_scores and embedding_scores.get(top_embedding, 0.0) >= 0.45:
            recommended = top_embedding
            confidence = min(0.85, max(0.45, embedding_scores[top_embedding]))
            method = "embedding_profile"
            reason = "Multilingual embedding similarity to a manual category profile."
        elif selected:
            recommended = selected
            confidence = 0.35 if hit_count == 0 else 0.45
            method = "selected_category_fallback"
            reason = "Text evidence is limited; kept your selected category."
        elif hit_count:
            recommended = top_keyword
            confidence = 0.45
            method = "keyword_rules"
            reason = f"Weak text signal: {keyword_hits[top_keyword][0]}."
        else:
            recommended = "Other"
            confidence = 0.2
            method = "unknown_fallback"
            reason = "No recognized maintenance terms; choose a category manually."

        if selected and selected == recommended and method != "selected_category_fallback":
            reason = f"{reason} It matches your selected category."
        return {
            "recommended_category": recommended,
            "confidence": round(confidence, 2),
            "method": method,
            "reason": reason,
            "selected_category": selected,
            "differs_from_selected": bool(selected and selected != recommended),
        }

    def recommend_priority(self, description: object, category: str | None) -> dict:
        text = normalize_ticket_text(description)
        for phrase, reason in SAFETY_INDICATORS:
            if _contains(text, phrase):
                return {"recommended_priority": "High", "method": "safety_rule", "reason": reason}
        if category == "Security":
            return {"recommended_priority": "High", "method": "context_rule", "reason": "Security requests receive high baseline urgency until staff triage."}
        if category in {"Electricity", "Lift", "Plumbing", "Internet"}:
            return {"recommended_priority": "Medium", "method": "context_rule", "reason": f"{category} requests receive medium baseline urgency until staff triage."}
        return {"recommended_priority": "Low", "method": "context_rule", "reason": "No deterministic safety indicator found; staff can still reprioritize."}

    def recommend(self, description: object, selected_category: str | None = None) -> dict:
        category = self.recommend_category(description, selected_category)
        return {"category": category, "priority": self.recommend_priority(description, category["recommended_category"])}
