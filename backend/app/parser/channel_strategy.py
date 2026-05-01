"""
channel_strategy.py — per-channel message preprocessing.

Each Telegram channel may publish price-lists in a unique format.
This module normalises that raw text BEFORE it reaches the regex/LLM parsers,
so the rest of the pipeline stays format-agnostic.

Supported strategies
--------------------
auto   - no transformation; regex runs first, LLM on fallback  (default)
regex  - no transformation; only regex parser is used
llm    - no transformation; only LLM parser is used
pipe   - lines are split by '|' into positional columns
table  - lines are split by tab / multiple spaces into positional columns

line_format hint (optional)
---------------------------
A pipe- or space-separated list of field names that describes the COLUMN ORDER
in each data line.  Supported field names:
  model  memory  color  condition  sim_type  price  currency  skip

Examples
  pipe  + line_format="model|memory|color|price"
  table + line_format="model memory price"

If line_format is absent the module tries to auto-detect columns by value type.

Output
------
preprocess_by_strategy() returns a string that looks like:
  "<model> <memory> <color> — <price>"
which is the canonical form the regex parser already handles well.
"""
from __future__ import annotations

import re
from typing import Optional

# Known memory sizes for column auto-detection
_MEMORY_VALUES = {"32", "64", "128", "256", "512", "1024", "2048",
                  "32gb", "64gb", "128gb", "256gb", "512gb", "1tb", "2tb"}
_PRICE_MIN = 1000  # anything below is not a price

# Strategies that require no text transformation
_PASSTHROUGH = {"auto", "regex", "llm"}


def preprocess_by_strategy(
    text: str,
    strategy: str,
    line_format: Optional[str] = None,
) -> str:
    """Return preprocessed message text ready for regex/LLM parsing."""
    if strategy in _PASSTHROUGH:
        return text
    if strategy == "pipe":
        return _transform_pipe(text, line_format)
    if strategy == "table":
        return _transform_table(text, line_format)
    # unknown strategy — passthrough
    return text


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_line_format(line_format: Optional[str]) -> list[str]:
    """Parse 'model|memory|color|price' or 'model memory price' -> list."""
    if not line_format:
        return []
    # normalise: replace | with space, strip, lowercase
    fmt = line_format.replace("|", " ").replace("\t", " ").lower()
    return [f.strip() for f in fmt.split() if f.strip()]


def _is_price(value: str) -> bool:
    """Heuristic: is this column value a price?"""
    clean = re.sub(r"[\s.,\u00a0\u202f]", "", value)
    clean = re.sub(r"[^\d]", "", clean)
    if not clean:
        return False
    try:
        return int(clean) >= _PRICE_MIN
    except ValueError:
        return False


def _is_memory(value: str) -> bool:
    """Heuristic: is this column value a memory/storage spec?"""
    v = value.strip().lower().replace(" ", "")
    # e.g. "256gb", "256", "1tb", "12/256"
    if v in _MEMORY_VALUES:
        return True
    if re.fullmatch(r"\d{2,4}gb", v):
        return True
    if re.fullmatch(r"\d+/\d+", v):  # RAM/storage combo
        return True
    return False


def _remap_columns(parts: list[str], field_order: list[str]) -> Optional[str]:
    """
    Map positional column values to named fields using field_order hint,
    then compose a canonical line: "<model> <memory> <color> — <price>".

    Returns None if a price column cannot be identified.
    """
    fields: dict[str, str] = {}

    if field_order and len(field_order) == len(parts):
        # Explicit mapping
        for name, value in zip(field_order, parts):
            if name != "skip":
                fields[name] = value.strip()
    else:
        # Auto-detect by value type
        remaining_model_parts: list[str] = []
        for part in parts:
            p = part.strip()
            if not p:
                continue
            if _is_price(p) and "price" not in fields:
                fields["price"] = p
            elif _is_memory(p) and "memory" not in fields:
                fields["memory"] = p
            else:
                remaining_model_parts.append(p)
        if remaining_model_parts:
            fields.setdefault("model", " ".join(remaining_model_parts))

    if "price" not in fields:
        return None  # can't do anything without a price

    # Build canonical line
    parts_out: list[str] = []
    if "model" in fields:
        parts_out.append(fields["model"])
    if "memory" in fields:
        parts_out.append(fields["memory"])
    if "color" in fields:
        parts_out.append(fields["color"])
    if "condition" in fields:
        parts_out.append(fields["condition"])
    if "sim_type" in fields:
        parts_out.append(fields["sim_type"])

    price_str = re.sub(r"[\s\u00a0\u202f]", "", fields["price"])
    price_str = price_str.rstrip("`'\"")

    canonical = " ".join(parts_out) + " — " + price_str
    return canonical.strip()


def _transform_lines(lines: list[str], separator_re: re.Pattern, field_order: list[str]) -> str:
    """Split each line by separator, remap, return joined result."""
    output_lines: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = separator_re.split(line)
        if len(parts) < 2:
            # single column — keep as-is for regex fallback
            output_lines.append(line)
            continue
        canonical = _remap_columns(parts, field_order)
        if canonical:
            output_lines.append(canonical)
        else:
            # keep original so LLM/regex can still try
            output_lines.append(line)
    return "\n".join(output_lines)


def _transform_pipe(text: str, line_format: Optional[str]) -> str:
    """Pipe strategy: split each line by '|'."""
    field_order = _parse_line_format(line_format)
    sep = re.compile(r"\s*\|\s*")
    lines = text.splitlines()
    return _transform_lines(lines, sep, field_order)


def _transform_table(text: str, line_format: Optional[str]) -> str:
    """Table strategy: split each line by tab or 2+ spaces."""
    field_order = _parse_line_format(line_format)
    sep = re.compile(r"\t|  +")  # tab OR 2+ spaces
    lines = text.splitlines()
    return _transform_lines(lines, sep, field_order)
