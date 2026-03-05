"""
tests/test_enhancements.py
---------------------------
Unit tests for the 4 enhancement features.
Run from D:\\final_v1\\backend\\ with:
    .venv\\Scripts\\python.exe -m pytest tests/test_enhancements.py -v
"""
import sys
import os

# Allow imports from backend root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================
# FEATURE 1 — module_detector.py
# ============================================================
from services.module_detector import detect_modules

class TestModuleDetector:

    def _chunk(self, module, similarity):
        return {"text": "some text", "module": module, "similarity": similarity, "distance": 1 - similarity}

    def test_above_threshold(self):
        chunks = [
            self._chunk("CIA Triad", 0.8),
            self._chunk("Cryptography", 0.6),
        ]
        result = detect_modules(chunks, threshold=0.5)
        assert result == ["CIA Triad", "Cryptography"]

    def test_below_threshold_excluded(self):
        chunks = [
            self._chunk("CIA Triad", 0.8),
            self._chunk("Low Relevance", 0.3),   # below 0.5
        ]
        result = detect_modules(chunks, threshold=0.5)
        assert result == ["CIA Triad"]
        assert "Low Relevance" not in result

    def test_duplicates_removed(self):
        chunks = [
            self._chunk("CIA Triad", 0.9),
            self._chunk("CIA Triad", 0.7),
            self._chunk("CIA Triad", 0.6),
        ]
        result = detect_modules(chunks, threshold=0.5)
        assert result == ["CIA Triad"]

    def test_unknown_module_excluded(self):
        chunks = [
            self._chunk("unknown", 0.9),
            self._chunk("None", 0.8),
            self._chunk("", 0.7),
            self._chunk(None, 0.7),
        ]
        result = detect_modules(chunks, threshold=0.5)
        assert result == []

    def test_empty_chunks(self):
        assert detect_modules([]) == []

    def test_no_chunks_above_threshold(self):
        chunks = [self._chunk("CIA Triad", 0.2)]
        assert detect_modules(chunks, threshold=0.5) == []

    def test_preserves_insertion_order(self):
        chunks = [
            self._chunk("Bravo", 0.9),
            self._chunk("Alpha", 0.8),
        ]
        result = detect_modules(chunks, threshold=0.5)
        assert result[0] == "Bravo"
        assert result[1] == "Alpha"


# ============================================================
# FEATURE 2 — bloom_classifier.py
# ============================================================
from services.bloom_classifier import classify_bloom

class TestBloomClassifier:

    def test_remember_level(self):
        r = classify_bloom("Define the term 'database'")
        assert r["bloom_level"] == "Remember"
        assert r["difficulty"] == "Easy"

    def test_understand_level(self):
        r = classify_bloom("Explain the working of TCP/IP protocol")
        assert r["bloom_level"] == "Understand"
        assert r["difficulty"] == "Easy"

    def test_apply_level(self):
        r = classify_bloom("Implement a bubble sort algorithm in Python")
        assert r["bloom_level"] == "Apply"
        assert r["difficulty"] == "Medium"

    def test_analyze_level(self):
        r = classify_bloom("Compare and differentiate RSA and AES encryption")
        assert r["bloom_level"] in ("Analyze", "Evaluate", "Create")  # "Compare" → Analyze
        assert r["bloom_level"] == "Analyze"

    def test_evaluate_level(self):
        r = classify_bloom("Justify the use of cloud computing for enterprise systems")
        assert r["bloom_level"] == "Evaluate"
        assert r["difficulty"] == "Hard"

    def test_create_level(self):
        r = classify_bloom("Design a secure network topology for a hospital")
        assert r["bloom_level"] == "Create"
        assert r["difficulty"] == "Hard"

    def test_unknown_fallback(self):
        r = classify_bloom("What is the CIA Triad?")
        # "What is" has no Bloom verb — should return Unknown
        assert r["bloom_level"] == "Unknown"
        assert r["difficulty"] == "Unknown"

    def test_higher_order_wins(self):
        # Contains both "list" (Remember) and "analyze" (Analyze)
        r = classify_bloom("List and analyze the properties of RSA")
        assert r["bloom_level"] == "Analyze"

    def test_case_insensitive(self):
        r = classify_bloom("DEFINE what encryption means")
        assert r["bloom_level"] == "Remember"

    def test_returns_dict_keys(self):
        r = classify_bloom("anything")
        assert "bloom_level" in r
        assert "difficulty" in r


# ============================================================
# FEATURE 3 — backward compat: analyze_question returns new keys
# ============================================================
from services.question_analyzer import analyze_question

class TestQuestionAnalyzerBackwardCompat:
    """
    Verify that analyze_question still returns all original keys
    AND the new enhanced keys, even when co_mapper is None.
    """

    def _make_chunk(self, sim, module="TestModule"):
        return {
            "text": "Intro to cryptography and security",
            "distance": 1 - sim,
            "similarity": sim,
            "module": module,
        }

    def test_original_keys_present_gatekeeper_fail(self):
        result = analyze_question(
            question="What is encryption?",
            similarity=0.05,       # below threshold → gatekeeper fails
            threshold=0.2,
            top_chunks=[self._make_chunk(0.05)],
            co_mapper=None,
        )
        assert "is_in_syllabus"    in result
        assert "gatekeeper_passed" in result
        assert "reason"            in result
        assert "llm"               in result
        assert result["is_in_syllabus"]    is False
        assert result["gatekeeper_passed"] is False

    def test_new_keys_present_gatekeeper_fail(self):
        result = analyze_question(
            question="Design a firewall",
            similarity=0.05,
            threshold=0.2,
            top_chunks=[],
            co_mapper=None,
        )
        assert "modules_detected" in result
        assert "bloom_level"      in result
        assert "difficulty"       in result
        assert "mapped_co"        in result
        assert isinstance(result["modules_detected"], list)
        assert result["mapped_co"] is None

    def test_bloom_in_result(self):
        result = analyze_question(
            question="Design a secure database schema",
            similarity=0.05,
            threshold=0.2,
            top_chunks=[],
            co_mapper=None,
        )
        # "Design" → Create level
        assert result["bloom_level"] == "Create"
        assert result["difficulty"]  == "Hard"

    def test_modules_detected_in_result(self):
        chunks = [
            self._make_chunk(0.9, "Cryptography"),
            self._make_chunk(0.7, "Network Security"),
            self._make_chunk(0.1, "Unrelated"),     # below 0.5 threshold
        ]
        result = analyze_question(
            question="Compare AES and RSA",
            similarity=0.05,
            threshold=0.2,
            top_chunks=chunks,
            co_mapper=None,
        )
        assert "Cryptography"    in result["modules_detected"]
        assert "Network Security" in result["modules_detected"]
        assert "Unrelated"       not in result["modules_detected"]


# ============================================================
# FEATURE 4 — config has new constant
# ============================================================
from config import MODULE_SIMILARITY_THRESHOLD

class TestConfig:
    def test_threshold_is_float(self):
        assert isinstance(MODULE_SIMILARITY_THRESHOLD, float)

    def test_threshold_in_valid_range(self):
        assert 0.0 <= MODULE_SIMILARITY_THRESHOLD <= 1.0
