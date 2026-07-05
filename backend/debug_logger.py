"""
debug_logger.py
----------------
Centralised debug logger for the Syllabus Validation Pipeline.

All debug output is gated behind DEBUG_MODE in config.py.
No functional code is touched — only log calls are added.

Usage:
    from debug_logger import dlog, dsection, dsummary, derror

    dsection("Router")                    # prints section header
    dlog("Router", "Detected type", val)  # prints keyed value
    dsummary("Ingestion", {...})          # prints a structured summary table
    derror("Parser", "reason text")       # prints a red-style error line
"""

from __future__ import annotations
import sys
import io

# Force stdout to UTF-8 so debug output with ⚠, →, ↳ etc.
# doesn't crash on Windows terminals using cp1252 encoding.
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
elif hasattr(sys.stdout, 'buffer'):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    from config import DEBUG_MODE
except ImportError:
    DEBUG_MODE = False


# ============================================================
# FORMATTING HELPERS
# ============================================================

_W = 54  # banner width


def _banner(title: str) -> str:
    return (
        "\n" + "=" * _W + "\n"
        f"  [{title}]\n"
        + "=" * _W
    )


def _kv(key: str, value) -> str:
    return f"  {key:<28} {value}"


def _divider() -> str:
    return "  " + "-" * (_W - 2)


# ============================================================
# PUBLIC API
# ============================================================

def dsection(tag: str) -> None:
    """Print a section banner if DEBUG_MODE is on."""
    if not DEBUG_MODE:
        return
    print(_banner(tag))


def dlog(tag: str, key: str, value=None) -> None:
    """Print a key=value debug line under a tag."""
    if not DEBUG_MODE:
        return
    if value is None:
        print(f"  [{tag}] {key}")
    else:
        print(_kv(f"[{tag}] {key}", value))


def dlist(tag: str, label: str, items: list) -> None:
    """Print a label followed by list items, indented."""
    if not DEBUG_MODE:
        return
    print(_kv(f"[{tag}] {label}", ""))
    for item in items:
        print(f"    - {item}")


def dtable(tag: str, rows: dict) -> None:
    """Print a compact key:value table."""
    if not DEBUG_MODE:
        return
    for k, v in rows.items():
        print(_kv(f"[{tag}] {k}", v))


def dsummary(title: str, rows: dict) -> None:
    """Print a structured summary block."""
    if not DEBUG_MODE:
        return
    print("\n" + "=" * _W)
    print(f"  {title.upper()}")
    print("=" * _W)
    for k, v in rows.items():
        print(_kv(k, v))
    print("=" * _W)


def derror(tag: str, message: str, reason: str = "") -> None:
    """Print an explicit error/failure message."""
    if not DEBUG_MODE:
        return
    print(f"\n  [ERROR][{tag}] {message}")
    if reason:
        print(f"    Reason: {reason}")


def ddivider(tag: str = "") -> None:
    """Print a visual divider."""
    if not DEBUG_MODE:
        return
    if tag:
        label = f"  -- {tag} --"
        print(label)
    else:
        print(_divider())
