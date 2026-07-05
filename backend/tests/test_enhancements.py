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
        r = classify_bloom("The CIA Triad.")
        # Has no Bloom verb or WH-question pattern — should return Unknown
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


# ============================================================
# FEATURE 5 — structured_curriculum_parser.py
# ============================================================
from processors.structured_curriculum_parser import (
    detect_document_format,
    derive_department,
    derive_program,
    parse_aicte_curriculum
)

class TestStructuredCurriculumParser:

    def test_detect_format(self):
        text_aicte = "Syllabus and Curricular Mapping, Course Objectives, Course Outcomes, CO-PO Mapping"
        text_single = "Subject Code: PEC-IT801B"
        text_unknown = "Random text"
        assert detect_document_format(text_aicte) == "AICTE"
        assert detect_document_format(text_single) == "SINGLE"
        assert detect_document_format(text_unknown) == "UNKNOWN"

    def test_derive_metadata(self):
        text = "Syllabus and Curricular Mapping for B.Tech in Information Technology"
        assert derive_program(text) == "B.Tech"
        assert derive_department(text, "PEC-IT801B") == "Information Technology"
        assert derive_department("", "PEC-CS601") == "Computer Science and Engineering"

    def test_parse_aicte_curriculum_success(self):
        text = """
        Syllabus and Curricular Mapping for B.Tech in Information Technology
        Semester VIII
        
        Course Title: Cryptography & Network Security
        Course Code: PEC-IT801B
        Semester: VIII
        
        Course Objectives:
        To secure network communication.
        
        Course Outcomes:
        CO1: Design secure frameworks.
        CO2: Analyze threat models.
        
        CO-PO Mapping:
        CO PO1 PO2 PO3 PO4 PO5
        CO1 3 2 - - 1
        CO2 2 3 1 - 2
        
        Units:
        Unit 1: Intro
        Introduction to security, plaintext.
        Unit 2: RSA
        Encryption techniques.
        
        References:
        1. Stallings, Cryptography.
        """
        results = parse_aicte_curriculum(text)
        assert len(results) == 1
        course = results[0]
        assert course["subject_name"] == "Cryptography & Network Security"
        assert course["subject_code"] == "PEC-IT801B"
        assert course["semester"] == "VIII"
        assert course["program"] == "B.Tech"
        assert course["department"] == "Information Technology"
        assert course["parser"] == "AICTE"
        assert course["parser_confidence"] == 0.97
        assert len(course["warnings"]) == 0
        
        # Check parsed structure
        parsed = course["parsed"]
        assert parsed["course_objectives"] == "To secure network communication."
        assert len(parsed["course_outcomes"]) == 2
        assert parsed["course_outcomes"][0]["co"] == "CO1"
        assert parsed["course_outcomes"][0]["bloom_level"] == "Create"  # Design -> Create
        assert parsed["co_po_mapping"]["CO1"]["PO1"] == 3
        assert len(parsed["units"]) == 2
        assert parsed["units"][0]["unit"] == "1"
        assert parsed["units"][0]["title"] == "Intro"
        assert parsed["units"][0]["content"] == "Introduction to security, plaintext."
        assert parsed["references"] == "1. Stallings, Cryptography."
        
        # Check parser metadata
        meta = course["parser_metadata"]
        assert meta["co_count"] == 2
        assert meta["po_mapping_count"] == 2
        assert meta["module_count"] == 2


# ============================================================
# FEATURE 6 — document_router.py
# ============================================================
from processors.document_router import detect_document_type

class TestDocumentRouter:

    def test_multi_subject_curriculum(self):
        text = (
            "Course Title: Cryptography & Network Security\n"
            "Course Outcomes: CO1 ...\n"
            "CO-PO Mapping: ...\n\n"
            "Course Title: Data Structures\n"
            "Course Outcomes: CO1 ...\n"
            "CO-PO Mapping: ...\n"
        )
        assert detect_document_type(text) == "MULTI_SUBJECT_CURRICULUM"

    def test_structured_subject_with_title_marker(self):
        text = (
            "Course Title: Cryptography & Network Security\n"
            "Course Outcomes: CO1 ...\n"
            "CO-PO Mapping: ...\n"
        )
        assert detect_document_type(text) == "STRUCTURED_SUBJECT"

    def test_structured_subject_no_title_marker(self):
        # No Course Title: marker but has 2+ structured indicators
        text = (
            "Course Outcomes: CO1 Understand encryption.\n"
            "CO-PO Mapping:\n"
            "CO1 PO1 PO2\n"
        )
        assert detect_document_type(text) == "STRUCTURED_SUBJECT"

    def test_legacy_subject(self):
        text = (
            "Semester VIII\n"
            "Module 1: Introduction to Networking\n"
            "This module covers OSI model and TCP/IP.\n"
        )
        assert detect_document_type(text) == "LEGACY_SUBJECT"

    def test_logs_source(self, capsys):
        detect_document_type("some text", source="PDF")
        captured = capsys.readouterr()
        assert "Input Source: PDF" in captured.out

    def test_course_name_variant(self):
        # "Course Name:" should also trigger MULTI_SUBJECT_CURRICULUM
        text = (
            "Course Name: Cryptography\n"
            "Outcomes: ...\n\n"
            "Course Name: Data Structures\n"
            "Outcomes: ...\n"
        )
        assert detect_document_type(text) == "MULTI_SUBJECT_CURRICULUM"


# ============================================================
# FEATURE 7 — curriculum_splitter.py
# ============================================================
from processors.curriculum_splitter import split_into_course_blocks

class TestCurriculumSplitter:

    def test_splits_into_blocks(self):
        text = (
            "Program Outcomes:\nPO1: Engineering knowledge.\n\n"
            "Course Title: Cryptography\nSome content here.\n\n"
            "Course Title: Data Structures\nOther content here.\n"
        )
        blocks = split_into_course_blocks(text)
        assert len(blocks) == 2

    def test_preamble_discarded(self):
        text = (
            "Vision: To be a leading department.\n"
            "Mission: Excellence in education.\n"
            "Program Outcomes: PO1 Engineering knowledge.\n\n"
            "Course Title: Cryptography\nContent here.\n"
        )
        blocks = split_into_course_blocks(text)
        assert len(blocks) == 1
        assert "Vision" not in blocks[0]
        assert "Mission" not in blocks[0]
        assert "Program Outcomes" not in blocks[0]

    def test_each_block_starts_with_title(self):
        text = (
            "Course Title: Cryptography\nContent A.\n\n"
            "Course Title: Networking\nContent B.\n\n"
            "Course Title: OS\nContent C.\n"
        )
        blocks = split_into_course_blocks(text)
        assert len(blocks) == 3
        for block in blocks:
            assert block.strip().lower().startswith("course title")

    def test_empty_text_returns_empty(self):
        assert split_into_course_blocks("") == []

    def test_no_title_markers_returns_empty(self):
        text = "Some random content without Course Title markers.\n"
        assert split_into_course_blocks(text) == []

    def test_course_name_variant(self):
        text = (
            "Course Name: Cryptography\nContent A.\n\n"
            "Course Name: OS\nContent B.\n"
        )
        blocks = split_into_course_blocks(text)
        assert len(blocks) == 2

