"""
Rule-based extraction of product offers from price message text.

Handles formats like:
  "Galaxy S26 Ultra 12/512 Jetblack SM-S948B/DS🇰🇿 - 94500"
  "15 Pro Max 256 nat - 915$"
  "iPhone 15 PM 256 Natural 91 500"
  "Apple 15 ProMax / 256 / white / new / 920 usd"
  "16/256 black esim 101000"
  "AirPods Pro 2 USB-C 14500"
  "Canon G7 X Mark III Silver - 88000"
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from app.parser.synonym_dict import (
    COLOR_ALIASES,
    CONDITION_ALIASES,
    CURRENCY_ALIASES,
    MEMORY_ALIASES,
    MODEL_ALIASES,
    SIM_TYPE_ALIASES,
)

logger = logging.getLogger(__name__)


@dataclass
class ParsedOffer:
    """Result of parsing a single offer line."""
    model: Optional[str] = None
    line: Optional[str] = None
    category: Optional[str] = None
    brand: str = "Unknown"
    memory: Optional[str] = None
    color: Optional[str] = None
    condition: str = "new"
    sim_type: Optional[str] = None
    price: Optional[float] = None
    currency: str = "RUB"
    confidence: float = 0.0
    raw_line: str = ""


@dataclass
class ParseResult:
    """Full result from parsing a message."""
    offers: list[ParsedOffer] = field(default_factory=list)
    unparsed_lines: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Price patterns — ordered by priority (most specific first)
# ---------------------------------------------------------------------------

# 1. Dash/arrow separator then price: " - 94500" / " — 915$" / " - 915 usd"
_PRICE_AFTER_DASH = re.compile(
    r'(?:^|\s)[—\-] ?\s*'
    r'(\d{1,3}(?:\s\d{3})*)'
    r'\s*(\$|€|₽|usd|eur|rub|руб|долл)?'
    r'(?=\s*(?:[\ud83c-\udfff]|$|\s|\b))',  # followed by emoji, EOL or space
    re.IGNORECASE | re.UNICODE,
)

# 2. Explicit currency symbol/word AFTER number: 915$, 920 usd
_PRICE_EXPLICIT_CURRENCY_AFTER = re.compile(
    r'(?<!\d)(\d{1,3}(?:\s\d{3})*)\s*(\$|€|₽|usd|eur|rub|руб|долл)(?:\b|$)',
    re.IGNORECASE,
)

# 3. Explicit currency BEFORE: $915, €1200
_PRICE_EXPLICIT_CURRENCY_BEFORE = re.compile(
    r'(\$|€|₽)\s*(\d{1,3}(?:\s\d{3})*)',
    re.IGNORECASE,
)

# 4. Space-separated large number: 91 500
_PRICE_SPACED = re.compile(
    r'(?<!\d)(\d{2,3}\s\d{3})(?:\b|$)',
)

# Memory pattern — used to exclude memory-like numbers from price matching
_MEMORY_PATTERN = re.compile(
    r'(?<![.\d])\b(32|64|128|256|512|1024)\s*(?:gb|гб)?\b(?!\s*(?:\$|€|₽|usd|eur|rub|руб))|(1|2)\s*(?:tb|тб)',
    re.IGNORECASE,
)

# RAM pattern in model names: 8/128, 12/256, 16/1TB — used to NOT confuse with price
_RAM_STORAGE_PATTERN = re.compile(
    r'\b\d{1,3}/(?:1tb|2tb|\d{2,4})\b',
    re.IGNORECASE,
)

# Pre-compile dictionary-based model patterns (sorted longest-first)
_SORTED_MODEL_KEYS = sorted(MODEL_ALIASES.keys(), key=len, reverse=True)

_MODEL_PATTERNS: list[tuple[re.Pattern, str]] = []
for _key in _SORTED_MODEL_KEYS:
    _escaped = re.escape(_key)
    _flexible = _escaped.replace(r'\ ', r'[\s/\-]*')
    _MODEL_PATTERNS.append((
        re.compile(r'(?:^|(?<=\s)|(?<=[/\-]))' + _flexible + r'(?=\s|[/\-]|$)', re.IGNORECASE),
        _key,
    ))


def parse_message(text: str) -> ParseResult:
    result = ParseResult()
    lines = _split_into_lines(text)

    for line in lines:
        stripped = line.strip()
        if not stripped or len(stripped) < 3:
            continue
        if _is_noise_line(stripped):
            continue

        offer = _parse_single_line(stripped)
        if offer and offer.model and offer.price and offer.price > 0:
            offer.raw_line = stripped
            result.offers.append(offer)
        elif stripped and len(stripped) > 5:
            result.unparsed_lines.append(stripped)

    return result


def _split_into_lines(text: str) -> list[str]:
    lines = text.split("\n")
    expanded = []
    for line in lines:
        parts = re.split(r'[;|]', line)
        expanded.extend(parts)
    return expanded


def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    lower = stripped.lower()

    # Separator lines
    if re.fullmatch(r'[-=_*~.]{3,}', stripped):
        return True

    # Markdown section headers: **...*  or __...__
    if re.match(r'^[*_]{1,3}[^*_].{0,60}[*_]{1,3}\s*$', stripped):
        return True

    # Lines with only emoji + text but no digits (section headers)
    if not any(c.isdigit() for c in stripped):
        return True

    # URLs
    if re.search(r'https?://', lower):
        return True

    # Phone numbers
    if re.search(r'\+7[\s\-]?\(?\d{3}\)?', stripped):
        return True
    if re.search(r'\b8[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}', stripped):
        return True

    # Known header/noise keywords at start
    noise_starts = [
        "прайс", "price list", "обновлен", "updated", "дата",
        "актуальный", "актуально", "на ", "от ", "#",
        "⬇️", "👇", "доставка", "оплата", "гарантия",
        "warranty", "контакты", "цены в канале", "t.me",
    ]
    for ns in noise_starts:
        if lower.startswith(ns):
            return True

    return False


def _parse_single_line(line: str) -> Optional[ParsedOffer]:
    offer = ParsedOffer()
    text = line

    # 1. Extract model
    model_info, model_span = _extract_model_with_span(text)
    remaining = text
    if model_info:
        offer.line, offer.model, offer.category = model_info
        offer.brand = _resolve_brand(offer.line)
        offer.confidence += 0.4
        if model_span:
            remaining = text[:model_span[0]] + " " + text[model_span[1]:]

    # 2. Extract price — always from FULL line to catch " - price" pattern
    price_val, currency, _ = _extract_price(text)
    if price_val is not None:
        offer.price = price_val
        offer.currency = currency

    # 3. Extract memory from remaining (after model stripped)
    memory = _extract_memory(remaining)
    if memory:
        offer.memory = memory
        offer.confidence += 0.2

    # 4. Color
    color = _extract_color(text)
    if color:
        offer.color = color
        offer.confidence += 0.1

    # 5. Condition
    condition = _extract_condition(text)
    if condition:
        offer.condition = condition

    # 6. SIM type
    sim_type = _extract_sim_type(text)
    if sim_type:
        offer.sim_type = sim_type

    if offer.price is not None:
        offer.confidence += 0.3

    offer.confidence = min(offer.confidence, 1.0)

    # Fallback: infer iPhone from shorthand like "16/256"
    if not offer.model:
        inferred = _infer_model_from_shorthand(line)
        if inferred:
            offer.line, offer.model, offer.category = inferred
            offer.brand = _resolve_brand(offer.line)
            offer.confidence = max(offer.confidence, 0.3)

    return offer


def _resolve_brand(line: Optional[str]) -> str:
    from app.parser.synonym_dict import LINE_TO_BRAND
    if not line:
        return "Unknown"
    return LINE_TO_BRAND.get(line, line.split()[0] if line else "Unknown")


def _extract_price(text: str) -> tuple[Optional[float], str, Optional[tuple[int, int]]]:
    """
    Extract price using prioritized patterns.
    Priority:
      1. " - 94500" / " — 915 usd" (dash separator)
      2. "915$" / "920 usd" (explicit currency after)
      3. "$915" (explicit currency before)
      4. "91 500" (spaced number >= 1000)
    """
    # Collect memory/RAM-like numbers to exclude from price matching
    memory_numbers: set[str] = set()
    for m in _MEMORY_PATTERN.finditer(text):
        memory_numbers.add(m.group(0).replace(" ", "").lower().rstrip("gbгбtbтб"))
    # Also exclude RAM/storage patterns like 12/256
    for m in _RAM_STORAGE_PATTERN.finditer(text):
        parts = re.split(r'/', m.group(0).lower())
        memory_numbers.update(p.rstrip("gtb") for p in parts)

    # --- Priority 1: dash separator ---
    for m in _PRICE_AFTER_DASH.finditer(text):
        num_str = m.group(1).replace(" ", "")
        curr_raw = (m.group(2) or "").lower()
        if num_str in memory_numbers:
            continue
        try:
            val = float(num_str)
        except ValueError:
            continue
        if val <= 0:
            continue
        currency = _resolve_currency(curr_raw) if curr_raw else "RUB"
        return val, currency, (m.start(), m.end())

    # --- Priority 2: explicit currency after number ---
    for m in _PRICE_EXPLICIT_CURRENCY_AFTER.finditer(text):
        num_str = m.group(1).replace(" ", "")
        curr_raw = m.group(2).lower()
        if num_str in memory_numbers:
            continue
        try:
            val = float(num_str)
        except ValueError:
            continue
        if val <= 0:
            continue
        return val, _resolve_currency(curr_raw), (m.start(), m.end())

    # --- Priority 3: explicit currency before number ---
    for m in _PRICE_EXPLICIT_CURRENCY_BEFORE.finditer(text):
        curr_raw = m.group(1).lower()
        num_str = m.group(2).replace(" ", "")
        if num_str in memory_numbers:
            continue
        try:
            val = float(num_str)
        except ValueError:
            continue
        if val <= 0:
            continue
        return val, _resolve_currency(curr_raw), (m.start(), m.end())

    # --- Priority 4: spaced number like "91 500" ---
    for m in _PRICE_SPACED.finditer(text):
        num_str = m.group(1).replace(" ", "")
        if num_str in memory_numbers:
            continue
        try:
            val = float(num_str)
        except ValueError:
            continue
        if val < 1000:
            continue
        return val, "RUB", (m.start(), m.end())

    return None, "RUB", None


def _resolve_currency(s: str) -> str:
    s = s.strip().lower()
    return CURRENCY_ALIASES.get(s, "RUB")


def _extract_model_with_span(text: str) -> tuple[Optional[tuple[str, str, str]], Optional[tuple[int, int]]]:
    lower = text.lower()
    normalized = re.sub(r'[/\-|•·]', ' ', lower)
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    # iPhone PM/P shorthands
    pm_match = re.search(r'(?:iphone\s*)?(\d{2})\s*pm\b', normalized, re.IGNORECASE)
    if pm_match:
        gen = pm_match.group(1)
        result = MODEL_ALIASES.get(f"{gen}pm")
        if result:
            return result, pm_match.span()

    p_match = re.search(r'(?:iphone\s*)?(\d{2})\s*p\b(?!\s*(?:r|l|h))', normalized, re.IGNORECASE)
    if p_match:
        gen = p_match.group(1)
        result = MODEL_ALIASES.get(f"{gen}p")
        if result:
            return result, p_match.span()

    for pattern, key in _MODEL_PATTERNS:
        m = pattern.search(normalized) or pattern.search(lower)
        if m:
            return MODEL_ALIASES[key], m.span()

    return None, None


def _extract_memory(text: str) -> Optional[str]:
    matches = list(_MEMORY_PATTERN.finditer(text))
    if not matches:
        return None
    for m in matches:
        if m.group(1):
            raw = m.group(1)
        else:
            raw = m.group(2) + "tb"
        return MEMORY_ALIASES.get(raw.lower(), raw.upper() + "GB")
    return None


def _extract_color(text: str) -> Optional[str]:
    lower = text.lower()
    # Remove digits so "256" doesn't interfere with color matching
    color_text = re.sub(r'\d+', ' ', lower)
    color_text = re.sub(r'[/\-|•·]', ' ', color_text)
    color_text = re.sub(r'\s+', ' ', color_text).strip()

    sorted_colors = sorted(COLOR_ALIASES.keys(), key=len, reverse=True)
    for alias in sorted_colors:
        pattern = r'(?:^|(?<=\s))' + re.escape(alias) + r'(?=\s|$)'
        if re.search(pattern, color_text):
            return COLOR_ALIASES[alias]
    return None


def _extract_condition(text: str) -> Optional[str]:
    lower = text.lower()
    sorted_conditions = sorted(CONDITION_ALIASES.keys(), key=len, reverse=True)
    for alias in sorted_conditions:
        if alias in lower:
            return CONDITION_ALIASES[alias]
    return None


def _extract_sim_type(text: str) -> Optional[str]:
    lower = text.lower()
    sorted_sims = sorted(SIM_TYPE_ALIASES.keys(), key=len, reverse=True)
    for alias in sorted_sims:
        if alias in lower:
            return SIM_TYPE_ALIASES[alias]
    return None


def _infer_model_from_shorthand(text: str) -> Optional[tuple[str, str, str]]:
    """Try to infer iPhone model from shorthand like '16/256' or '16 256'."""
    patterns = [
        re.compile(r'(?<!\d)(1[2-6])\s*[/\-]\s*(64|128|256|512|1024)', re.IGNORECASE),
        re.compile(r'(?<!\d)(1[2-6])\s+(64|128|256|512|1024)', re.IGNORECASE),
    ]
    for pat in patterns:
        m = pat.search(text)
        if m:
            gen = m.group(1)
            key = f"iphone {gen}"
            if key in MODEL_ALIASES:
                return MODEL_ALIASES[key]
    return None


def parse_message_to_offers(text: str) -> list[ParsedOffer]:
    result = parse_message(text)
    return result.offers
