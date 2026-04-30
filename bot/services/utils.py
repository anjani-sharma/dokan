"""Shared helpers for AI service calls."""
import json
import re
import time
from typing import Any


def parse_json_response(raw: str) -> Any:
    """
    Safely extract JSON from a Claude response.
    Handles markdown fences, leading/trailing text, and partial responses.
    """
    raw = raw.strip()

    # Strip ```json ... ``` or ``` ... ``` fences
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()

    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Find the first { or [ and try from there
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = raw.find(start_char)
        end = raw.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass

    raise ValueError(f"Could not extract JSON from response: {raw[:200]}")


def with_retry(fn, retries: int = 2, delay: float = 1.0):
    """Call fn up to retries+1 times, sleeping delay seconds between attempts."""
    last_exc = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt < retries:
                time.sleep(delay)
    raise last_exc
