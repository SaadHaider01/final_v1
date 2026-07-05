"""
processors/curriculum_splitter.py
-----------------------------------
Curriculum block splitter.

Responsibility: Split a MULTI_SUBJECT_CURRICULUM text into individual
course text blocks, one per course. Discards everything before the first
Course Title marker (preamble: Vision, Mission, POs, PSOs, etc.).

The splitter does NOT extract any metadata.
It only isolates text boundaries so each block can be sent to the
Structured Curriculum Parser independently.
"""

import re

# -----------------------------------------------------------
# COURSE TITLE MARKER — same pattern as document_router
# Uses \s* between words to handle PDF extraction artefacts
# (e.g. "CourseTitle:" instead of "Course Title:")
# -----------------------------------------------------------
_COURSE_TITLE_MARKER = re.compile(
    r"^\s*(?:Course\s*Title|Course\s*Name|Paper\s*Title|Subject\s*Title)\s*[:\-]",
    re.IGNORECASE | re.MULTILINE,
)

# Regex to extract the title text after the marker for logging
_TITLE_TEXT_RE = re.compile(
    r"(?:Course\s*Title|Course\s*Name|Paper\s*Title|Subject\s*Title)\s*[:\-]\s*(.+)",
    re.IGNORECASE,
)


def split_into_course_blocks(text: str) -> list:
    """
    Split a multi-subject curriculum into a list of raw text blocks.

    Each block starts at a "Course Title:" marker and ends just before
    the next marker (or at EOF). Everything before the first marker is
    discarded entirely.

    Args:
        text: Full extracted plain text of the curriculum document.

    Returns:
        List of raw text strings, one per course. May be empty if no
        Course Title markers are found.
    """
    print("[Splitter] Splitting...")

    lines = text.split("\n")
    blocks = []
    current_block_lines = []
    in_block = False

    for line in lines:
        if _COURSE_TITLE_MARKER.match(line):
            # Save the previous block if we were building one
            if in_block and current_block_lines:
                block_text = "\n".join(current_block_lines).strip()
                if block_text:
                    blocks.append(block_text)
                    # Log the title of this completed block
                    _log_block_title(block_text, len(blocks))

            # Start a new block
            current_block_lines = [line]
            in_block = True
        elif in_block:
            current_block_lines.append(line)

    # Don't forget the final block
    if in_block and current_block_lines:
        block_text = "\n".join(current_block_lines).strip()
        if block_text:
            blocks.append(block_text)
            _log_block_title(block_text, len(blocks))

    print(f"[Splitter] Total course blocks extracted: {len(blocks)}")
    return blocks


def _log_block_title(block_text: str, block_index: int) -> None:
    """Extract and log the Course Title from the first line of a block."""
    first_line = block_text.split("\n")[0] if block_text else ""
    title_match = _TITLE_TEXT_RE.search(first_line)
    title = title_match.group(1).strip() if title_match else "(unknown)"
    print(f"[Splitter] Routing Block {block_index} (Course Title: {title})")
