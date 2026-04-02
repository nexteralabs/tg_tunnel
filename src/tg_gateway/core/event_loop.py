"""
Event loop policy management utilities.

Handles platform-specific event loop policy setup following best practices.
Should be called once, early, before any async operations.
"""

import os
import asyncio


def set_event_loop_policy():
    """
    Set the appropriate event loop policy for the current platform.

    - Windows: Uses WindowsSelectorEventLoopPolicy for compatibility with libraries
      that need add_reader/fileno (like aiogram, psycopg)
    - Linux/macOS: Uses default Selector-based event loop (no change needed)

    Should be called once at the beginning of each entry point, before any
    async operations, bot creation, or uvicorn startup.
    """
    if os.name == "nt":  # Windows
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
