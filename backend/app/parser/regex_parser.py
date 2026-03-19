"""
Rule-based extraction of product offers from price message text.

Handles formats like:
  "15 Pro Max 256 nat - 915$"
  "iPhone 15 PM 256 Natural 91 500"
  "Apple 15 ProMax / 256 / white / new / 920 usd"
  "16/256 black esim 101000"
  "AirPods Pro 2 USB-C 14500"
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
    line: Optional[str] = None       # iPhone, AirPods, etc.
    category: Optional[str] = None   # smartphone, headphones, etc.
    brand: str = "Apple"
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


# ---- Price patterns ----

_PRICE_PATTERNS = [
    # Price with explicit currency symbol/word after: 915$, 920 usd, 14500₽
    re.compile(
        r'(\d{1,3}(?:\s\d{3})*)\s*(\$|€|₽|usd|eur|rub|руб|долл)(?:\b|$|(?=\s))',
        re.IGNORECASE,
    ),
    # Price with currency before: $915
    re.compile(
        r'(\$|€|₽)\s*(\d{1,3}(?:\s\d{3})*)',
        re.IGNORECASE,
    ),
    # Large number without currency (RUB assumed): 91 500
    re.compile(
        r'(?<!\d)(\d{2,3}\s\d{3})(?:\b|$)',
    ),
    # Standalone large number (>=5 digits, not memory) at end of string
    re.compile(
        r'(?<!\d)(\d{5,7})(?!\s*(?:gb|tb|гб|тб))(?:\s*₽|\s*р\.?)?\s*$',
        re.IGNORECASE,
    ),
    # Standalone large number (4-7 digits) anywhere, not memory
    re.compile(
        r'(?<!\d)(\d{4,7})(?!\s*(?:gb|tb|гб|тб))(?=\s|$)',
        re.IGNORECASE,
    ),
]

# ---- Memory patterns ----
_MEMORY_PATTERN = re.compile(
    r'(?<![.\d])\b(32|64|128|256|512|1024)\s*(?:gb|гб)?\b(?!\s*(?:\$|€|₽|usd|eur|rub|руб))|(1|2)\s*(?:tb|тб)',
    re.IGNORECASE,
)

# ---- Expanded model aliases for PM/P abbreviations ----
_SHORTHAND_MODEL_PATTERNS: list[tuple[re.Pattern, tuple[str, str, str]]] = [
    (re.compile(r'(?:iphone\s*)?(\d{2})\s*pm\b', re.IGNORECASE), None),
    (re.compile(r'(?:iphone\s*)?(\d{2})\s*p\b(?!\s*r)', re.IGNORECASE), None),
]


def _resolve_shorthand_model(match: re.Match, is_pm: bool) -> Optional[tuple[str, str, str]]:
    """Resolve a PM/P shorthand match to a model tuple."""
    gen = match.group(1)
    key = f"{gen}pm" if is_pm else f"{gen}p"
    return MODEL_ALIASES.get(key)


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
    """
    Parse a price message and extract all offers.
    Splits multi-line messages and processes each line independently.
    """
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
    """Split message text into individual offer lines."""
    lines = text.split("\n")
    expanded = []
    for line in lines:
        parts = re.split(r'[;|]', line)
        expanded.extend(parts)
    return expanded


def _is_noise_line(line: str) -> bool:
    """Check if a line is a header, separator, URL, phone number, or noise."""
    stripped = line.strip().lower()

    # Separator lines
    if re.fullmatch(r'[-=_*~.]{3,}', stripped):
        return True

    # Too short with no digits
    if len(stripped) < 5 and not any(c.isdigit() for c in stripped):
        return True

    # URLs — always noise, no price data
    if re.search(r'https?://', stripped):
        return True

    # Phone numbers — 7-digit strings that would match price patterns
    if re.search(r'\+7[\s\-]?\(?\d{3}\)?', stripped):
        return True
    if re.search(r'\b8[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}', stripped):
        return True

    # Known header/noise keywords
    noise_starts = [
        "прайс", "price list", "обновлен", "updated", "дата",
        "актуальный", "актуально", "на ", "от ", "#", "📱", "🔥",
        "⬇️", "👇", "доставка", "оплата", "гарантия", "warranty",
        "контакты", "цены в канале", "t.me",
    ]
    for ns in noise_starts:
        if stripped.startswith(ns):
            return True

    return False


def _parse_single_line(line: str) -> Optional[ParsedOffer]:
    """Parse a single line into a ParsedOffer."""
    offer = ParsedOffer()
    text = line

    # 1. Extract model FIRST to identify which parts of text are model name
    model_info, model_span = _extract_model_with_span(text)
    remaining = text
    if model_info:
        offer.line, offer.model, offer.category = model_info
        offer.confidence += 0.4
        if model_span:
            remaining = text[:model_span[0]] + " " + text[model_span[1]:]

    # 2. Extract price from remaining text
    price_val, currency, price_span = _extract_price(remaining)
    if price_val is not None:
        offer.price = price_val
        offer.currency = currency

    # 3. Extract memory
    memory = _extract_memory(remaining)
    if memory:
        offer.memory = memory
        offer.confidence += 0.2

    # 4. Extract color
    color = _extract_color(text)
    if color:
        offer.color = color
        offer.confidence += 0.1

    # 5. Extract condition
    condition = _extract_condition(text)
    if condition:
        offer.condition = condition

    # 6. Extract SIM type
    sim_type = _extract_sim_type(text)
    if sim_type:
        offer.sim_type = sim_type

    # 7. Price contributes to confidence
    if offer.price is not None:
        offer.confidence += 0.3

    offer.confidence = min(offer.confidence, 1.0)

    # If no model was found, try to infer from shorthand like "16/256"
    if not offer.model:
        inferred = _infer_model_from_shorthand(line)
        if inferred:
            offer.line, offer.model, offer.category = inferred
            offer.confidence = max(offer.confidence, 0.3)

    return offer


def _extract_price(text: str) -> tuple[Optional[float], str, Optional[tuple[int, int]]]:
    """
    Extract price and currency from text.
    Returns (price_value, currency_code, (start, end)) or (None, "RUB", None).
    """
    best_price: Optional[float] = None
    best_currency = "RUB"
    best_span: Optional[tuple[int, int]] = None

    pat = _PRICE_PATTERNS[0]
    for m in pat.finditer(text):
        num_str = m.group(1).replace(" ", "")
        curr_str = m.group(2).lower()
        try:
            val = float(num_str)
        except ValueError:
            continue
        currency = _resolve_currency(curr_str)
        best_price = val
        best_currency = currency
        best_span = (m.start(), m.end())

    if best_price is None:
        pat = _PRICE_PATTERNS[1]
        for m in pat.finditer(text):
            curr_str = m.group(1).lower()
            num_str = m.group(2).replace(" ", "")
            try:
                val = float(num_str)
            except ValueError:
                continue
            currency = _resolve_currency(curr_str)
            best_price = val
            best_currency = currency
            best_span = (m.start(), m.end())

    if best_price is None:
        pat = _PRICE_PATTERNS[2]
        for m in pat.finditer(text):
            num_str = m.group(1).replace(" ", "")
            try:
                val = float(num_str)
            except ValueError:
                continue
            if val >= 1000:
                best_price = val
                best_currency = "RUB"
                best_span = (m.start(), m.end())

    if best_price is None:
        pat = _PRICE_PATTERNS[3]
        for m in pat.finditer(text):
            num_str = m.group(1).replace(" ", "")
            try:
                val = float(num_str)
            except ValueError:
                continue
            if val >= 1000 and num_str not in ("1024",):
                best_price = val
                best_currency = "RUB"
                best_span = (m.start(), m.end())

    return best_price, best_currency, best_span


def _resolve_currency(s: str) -> str:
    """Resolve currency string to standard code."""
    s = s.strip().lower()
    return CURRENCY_ALIASES.get(s, "RUB")


def _extract_model_with_span(text: str) -> tuple[Optional[tuple[str, str, str]], Optional[tuple[int, int]]]:
    """
    Extract product model from text, returning result and span.
    Returns ((line, model, category), (start, end)) or (None, None).
    """
    lower = text.lower()
    normalized = re.sub(r'[/\-|\u2022\u00b7]', ' ', lower)
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    pm_match = re.search(r'(?:iphone\s*)?(\d{2})\s*pm\b', normalized, re.IGNORECASE)
    if pm_match:
        result = _resolve_shorthand_model(pm_match, is_pm=True)
        if result:
            return result, pm_match.span()

    p_match = re.search(r'(?:iphone\s*)?(\d{2})\s*p\b(?!\s*(?:r|l|h))', normalized, re.IGNORECASE)
    if p_match:
        result = _resolve_shorthand_model(p_match, is_pm=False)
        if result:
            return result, p_match.span()

    for pattern, key in _MODEL_PATTERNS:
        m = pattern.search(normalized)
        if m:
            return MODEL_ALIASES[key], m.span()
        m = pattern.search(lower)
        if m:
            return MODEL_ALIASES[key], m.span()

    return None, None


def _extract_model(text: str) -> Optional[tuple[str, str, str]]:
    """Extract product model from text (without span)."""
    result, _ = _extract_model_with_span(text)
    return result


def _extract_memory(text: str) -> Optional[str]:
    """Extract memory/storage specification."""
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
    """Extract color from text."""
    lower = text.lower()
    color_text = re.sub(r'\d+', ' ', lower)
    color_text = re.sub(r'[/\-|\u2022\u00b7]', ' ', color_text)
    color_text = re.sub(r'\s+', ' ', color_text).strip()

    sorted_colors = sorted(COLOR_ALIASES.keys(), key=len, reverse=True)
    for alias in sorted_colors:
        pattern = r'(?:^|(?<=\s))' + re.escape(alias) + r'(?=\s|$)'
        if re.search(pattern, color_text):
            return COLOR_ALIASES[alias]

    return None


def _extract_condition(text: str) -> Optional[str]:
    """Extract product condition."""
    lower = text.lower()
    sorted_conditions = sorted(CONDITION_ALIASES.keys(), key=len, reverse=True)
    for alias in sorted_conditions:
        if alias in lower:
            return CONDITION_ALIASES[alias]
    return None


def _extract_sim_type(text: str) -> Optional[str]:
    """Extract SIM type."""
    lower = text.lower()
    sorted_sims = sorted(SIM_TYPE_ALIASES.keys(), key=len, reverse=True)
    for alias in sorted_sims:
        if alias in lower:
            return SIM_TYPE_ALIASES[alias]
    return None


def _infer_model_from_shorthand(text: str) -> Optional[tuple[str, str, str]]:
    """Try to infer model from shorthand like '16/256' or '16 256'."""
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
    """Convenience function: parse and return only successful offers."""
    result = parse_message(text)
    return result.offers
