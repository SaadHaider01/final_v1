"""
processors/curriculum_splitter.py
-----------------------------------
Curriculum block splitter.

Splits a MULTI_SUBJECT_CURRICULUM into individual course text blocks.
Discards everything before the first Course Title marker (preamble).
Does NOT extract any metadata.
"""

import re
from debug_logger import dsection, dlog, ddivider, derror

# -----------------------------------------------------------
# COURSE TITLE MARKER
# Uses \s* to handle PDF artefacts ("CourseTitle:" vs "Course Title:")
# -----------------------------------------------------------
_COURSE_TITLE_MARKER = re.compile(
    r"^\s*(?:Course\s*Title|Course\s*Name|Paper\s*Title|Subject\s*Title)\s*[:\-]",
    re.IGNORECASE | re.MULTILINE,
)

_TITLE_TEXT_RE = re.compile(
    r"(?:Course\s*Title|Course\s*Name|Paper\s*Title|Subject\s*Title)\s*[:\-]\s*(.+)",
    re.IGNORECASE,
)


def split_into_course_blocks(text: str) -> list:
    """
    Split a multi-subject curriculum into a list of raw text blocks,
    one per course. Everything before the first Course Title marker is discarded.
    """
    dsection("Splitter")
    dlog("Splitter", "Input length", f"{len(text):,} chars")

    lines = text.split("\n")
    blocks = []
    current_block_lines = []
    block_start_offset = 0
    current_offset = 0
    in_block = False

    # Track character offsets for debug
    block_offsets = []     # list of (start, end) char positions
    char_pos = 0

    for line in lines:
        line_len = len(line) + 1   # +1 for \n
        if _COURSE_TITLE_MARKER.match(line):
            if in_block and current_block_lines:
                block_text = "\n".join(current_block_lines).strip()
                if block_text:
                    blocks.append(block_text)
                    block_offsets.append((block_start_offset, char_pos))
            current_block_lines = [line]
            block_start_offset = char_pos
            in_block = True
        elif in_block:
            current_block_lines.append(line)
        char_pos += line_len

    # Final block
    if in_block and current_block_lines:
        block_text = "\n".join(current_block_lines).strip()
        if block_text:
            blocks.append(block_text)
            block_offsets.append((block_start_offset, char_pos))

    # --- Debug output ---
    if not blocks:
        derror("Splitter", "No course blocks found",
               "No Course Title markers detected — check if markers were stripped by PDF extractor")
    else:
        dlog("Splitter", "Course Title markers found", len(blocks))
        dlog("Splitter", "Preamble discarded", f"first {block_offsets[0][0] if block_offsets else 0:,} chars")
        for i, (block_text, (start, end)) in enumerate(zip(blocks, block_offsets)):
            title = _extract_title(block_text)
            dlog("Splitter", f"Block {i+1}", f"chars {start:,} -> {end:,}  ({end - start:,} chars)")
            dlog("Splitter", f"  Title", title)

    return blocks


def _extract_title(block_text: str) -> str:
    """Extract and return the Course Title from the first line of a block."""
    first_line = block_text.split("\n")[0] if block_text else ""
    m = _TITLE_TEXT_RE.search(first_line)
    return m.group(1).strip() if m else "(unknown)"
