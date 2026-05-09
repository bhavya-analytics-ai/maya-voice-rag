"""
sprint7/clock/inject.py
Phase 0 — clock awareness.
Call get_clock_string() and prepend to any system prompt.
"""
from datetime import datetime


def get_clock_string() -> str:
    now = datetime.now()
    return f"[Current date/time: {now.strftime('%A, %B %d, %Y %H:%M')}]\n"
