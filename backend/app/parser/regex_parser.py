"""
Rule-based extraction of product offers from price message text.

Supported price formats:
  "Galaxy S26 Ultra 12/512 Jetblack - 94500"
  "17 Pro 256 Blue eSim 🇯🇵 - 96.500*"
  "15 Pro Max 256 nat - 915$"
  "iPhone 15 PM 256 Natural 91 500"
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
    offers: list[ParsedOffer] = field(default_factory=list)
    unparsed_lines: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Price helpers
# ---------------------------------------------------------------------------

def _normalize_price_str(s: str) -> str:
    """
    Normalize price string to plain integer string.
    Handles:
      - dot-as-thousands-separator: "62.000" -> "62000"
      - space-as-thousands-separator: "62 000" -> "62000"
      - trailing asterisk/garbage: "96.500*" -> "96500"
    """
    # Strip trailing non-digit chars (*, ’, etc.)
    s = re.sub(r'[^\d.,]', '', s)
    # If dot is used as thousands separator: N.NNN or N.NNN.NNN
    if re.match(r'^\d{1,3}(?:\.\d{3})+$', s):
        s = s.replace('.', '')
    # If comma is thousands separator: N,NNN
    elif re.match(r'^\d{1,3}(?:,\d{3})+$', s):
        s = s.replace(',', '')
    else:
        # Remove any remaining separators
        s = s.replace('.', '').replace(',', '')
    return s


# ---------------------------------------------------------------------------
# Price patterns (priority order)
# ---------------------------------------------------------------------------

# 1. Dash/em-dash separator: " - 94500" / " - 96.500*" / " — 915 usd"
_PRICE_AFTER_DASH = re.compile(
    r'(?:^|\s)[—\-]\s*'
    r'(\d{1,3}(?:[.,]\d{3})*(?:\s\d{3})*\d*)'
    r'\*?'                          # optional trailing asterisk
    r'\s*(\$|€|₽|usd|eur|rub|руб|долл)?'
    r'(?=[^\d]|$)',
    re.IGNORECASE | re.UNICODE,
)

# 2. Explicit currency after: 915$, 920 usd
_PRICE_EXPLICIT_AFTER = re.compile(
    r'(?<!\d)(\d{1,3}(?:[.,]\d{3})*|\d{4,7})\s*(\$|€|₽|usd|eur|rub|руб|долл)(?:\b|$)',
    re.IGNORECASE,
)

# 3. Explicit currency before: $915
_PRICE_EXPLICIT_BEFORE = re.compile(
    r'(\$|€|₽)\s*(\d{1,3}(?:[.,]\d{3})*|\d{4,7})',
    re.IGNORECASE,
)

# 4. Spaced thousands: "91 500"
_PRICE_SPACED = re.compile(
    r'(?<!\d)(\d{2,3}\s\d{3})(?:\b|$)',
)

# Memory pattern
_MEMORY_PATTERN = re.compile(
    r'(?<![.\d])\b(32|64|128|256|512|1024)\s*(?:gb|гб)?\b(?!\s*(?:\$|€|₽|usd|eur|rub|руб))'
    r'|(1|2)\s*(?:tb|тб)',
    re.IGNORECASE,
)

# RAM/Storage ratio pattern (e.g. 12/256, 8/128, 16/1TB) — exclude from price
_RAM_STORAGE_PATTERN = re.compile(
    r'\b\d{1,3}/(?:1tb|2tb|\d{2,4})\b',
    re.IGNORECASE,
)

# Pre-compile model patterns (longest-first)
_SORTED_MODEL_KEYS = sorted(MODEL_ALIASES.keys(), key=len, reverse=True)
_MODEL_PATTERNS: list[tuple[re.Pattern, str]] = []
for _key in _SORTED_MODEL_KEYS:
    _escaped = re.escape(_key)
    _flexible = _escaped.replace(r'\ ', r'[\s/\-]*')
    _MODEL_PATTERNS.append((
        re.compile(r'(?:^|(?<=\s)|(?<=[/\-]))' + _flexible + r'(?=\s|[/\-]|$)', re.IGNORECASE),
        _key,
    ))


# ---------------------------------------------------------------------------
# Noise line patterns
# ---------------------------------------------------------------------------
_NOISE_PATTERNS = [
    re.compile(r'^[-=_*~.]{3,}$'),                          # separators
    re.compile(r'^[*_]{1,3}[^*_].{0,80}[*_]{1,3}\s*$'),    # **header**
    re.compile(r'https?://', re.IGNORECASE),                 # URLs
    re.compile(r'\+7[\s\-]?\(?\d{3}\)?'),                    # phone RU
    re.compile(r'\b8[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}'),       # phone RU alt
    re.compile(                                              # bot button lines
        r'(?:нажмите|кнопку|прайс открыт|прайс закрыт)',
        re.IGNORECASE,
    ),
]

_NOISE_STARTS = [
    "прайс", "price list", "обновлен", "updated", "дата",
    "актуальный", "актуально", "на ", "от ", "#",
    "⬇️", "👇", "доставка", "оплата", "гарантия",
    "warranty", "контакты", "цены в канале", "t.me",
]

# Chat-like messages: short lines without product keywords
_CHAT_KEYWORDS = [
    "привет", "даров", "как дают", "как пишут", "да?", "есть?",
    "hello", "hi ", "hey ", "thanks", "спасиб", "бро",
]


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

    # Compiled noise patterns
    for pat in _NOISE_PATTERNS:
        if pat.search(stripped):
            return True

    # Lines with zero digits are almost certainly not price offers
    if not any(c.isdigit() for c in stripped):
        return True

    # Known noise prefixes
    for ns in _NOISE_STARTS:
        if lower.startswith(ns):
            return True

    # Chat-like content in short lines
    if len(stripped) < 60:
        for kw in _CHAT_KEYWORDS:
            if kw in lower:
                return True

    return False


def _parse_single_line(line: str) -> Optional[ParsedOffer]:
    offer = ParsedOffer()
    text = line

    model_info, model_span = _extract_model_with_span(text)
    remaining = text
    if model_info:
        offer.line, offer.model, offer.category = model_info
        offer.brand = _resolve_brand(offer.line)
        offer.confidence += 0.4
        if model_span:
            remaining = text[:model_span[0]] + " " + text[model_span[1]:]

    # Price from full line (to capture " - price" at end)
    price_val, currency, _ = _extract_price(text)
    if price_val is not None:
        offer.price = price_val
        offer.currency = currency

    memory = _extract_memory(remaining)
    if memory:
        offer.memory = memory
        offer.confidence += 0.2

    color = _extract_color(text)
    if color:
        offer.color = color
        offer.confidence += 0.1

    condition = _extract_condition(text)
    if condition:
        offer.condition = condition

    sim_type = _extract_sim_type(text)
    if sim_type:
        offer.sim_type = sim_type

    if offer.price is not None:
        offer.confidence += 0.3

    offer.confidence = min(offer.confidence, 1.0)

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
    # Collect numbers to exclude (memory/RAM sizes)
    excluded: set[str] = set()
    for m in _MEMORY_PATTERN.finditer(text):
        excluded.add(re.sub(r'[^\d]', '', m.group(0)))
    for m in _RAM_STORAGE_PATTERN.finditer(text):
        for part in re.split(r'/', m.group(0).lower()):
            excluded.add(re.sub(r'[^\d]', '', part))

    def _try_parse(num_str: str, curr_raw: str) -> Optional[tuple[float, str]]:
        normalized = _normalize_price_str(num_str)
        if normalized in excluded:
            return None
        try:
            val = float(normalized)
        except ValueError:
            return None
        if val <= 0:
            return None
        currency = _resolve_currency(curr_raw) if curr_raw else "RUB"
        return val, currency

    # Priority 1: dash separator
    for m in _PRICE_AFTER_DASH.finditer(text):
        result = _try_parse(m.group(1), (m.group(2) or "").lower())
        if result:
            return result[0], result[1], (m.start(), m.end())

    # Priority 2: explicit currency after
    for m in _PRICE_EXPLICIT_AFTER.finditer(text):
        result = _try_parse(m.group(1), m.group(2).lower())
        if result:
            return result[0], result[1], (m.start(), m.end())

    # Priority 3: explicit currency before
    for m in _PRICE_EXPLICIT_BEFORE.finditer(text):
        result = _try_parse(m.group(2), m.group(1).lower())
        if result:
            return result[0], result[1], (m.start(), m.end())

    # Priority 4: spaced thousands
    for m in _PRICE_SPACED.finditer(text):
        result = _try_parse(m.group(1), "")
        if result and result[0] >= 1000:
            return result[0], result[1], (m.start(), m.end())

    return None, "RUB", None


def _resolve_currency(s: str) -> str:
    return CURRENCY_ALIASES.get(s.strip().lower(), "RUB")


def _extract_model_with_span(text: str) -> tuple[Optional[tuple[str, str, str]], Optional[tuple[int, int]]]:
    lower = text.lower()
    normalized = re.sub(r'[/\-|•·]', ' ', lower)
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    # iPhone PM/P shorthands
    pm_match = re.search(r'(?:iphone\s*)?(\d{2})\s*pm\b', normalized, re.IGNORECASE)
    if pm_match:
        result = MODEL_ALIASES.get(f"{pm_match.group(1)}pm")
        if result:
            return result, pm_match.span()

    p_match = re.search(r'(?:iphone\s*)?(\d{2})\s*p\b(?!\s*(?:r|l|h))', normalized, re.IGNORECASE)
    if p_match:
        result = MODEL_ALIASES.get(f"{p_match.group(1)}p")
        if result:
            return result, p_match.span()

    for pattern, key in _MODEL_PATTERNS:
        m = pattern.search(normalized) or pattern.search(lower)
        if m:
            return MODEL_ALIASES[key], m.span()

    return None, None


def _extract_memory(text: str) -> Optional[str]:
    matches = list(_MEMORY_PATTERN.finditer(text))
    for m in matches:
        raw = m.group(1) if m.group(1) else m.group(2) + "tb"
        return MEMORY_ALIASES.get(raw.lower(), raw.upper() + "GB")
    return None


def _extract_color(text: str) -> Optional[str]:
    lower = text.lower()
    color_text = re.sub(r'\d+', ' ', lower)
    color_text = re.sub(r'[/\-|•·]', ' ', color_text)
    color_text = re.sub(r'\s+', ' ', color_text).strip()
    sorted_colors = sorted(COLOR_ALIASES.keys(), key=len, reverse=True)
    for alias in sorted_colors:
        if re.search(r'(?:^|(?<=\s))' + re.escape(alias) + r'(?=\s|$)', color_text):
            return COLOR_ALIASES[alias]
    return None


def _extract_condition(text: str) -> Optional[str]:
    lower = text.lower()
    for alias in sorted(CONDITION_ALIASES.keys(), key=len, reverse=True):
        if alias in lower:
            return CONDITION_ALIASES[alias]
    return None


def _extract_sim_type(text: str) -> Optional[str]:
    lower = text.lower()
    for alias in sorted(SIM_TYPE_ALIASES.keys(), key=len, reverse=True):
        if alias in lower:
            return SIM_TYPE_ALIASES[alias]
    return None


def _infer_model_from_shorthand(text: str) -> Optional[tuple[str, str, str]]:
    for pat in [
        re.compile(r'(?<!\d)(1[2-7])\s*[/\-]\s*(64|128|256|512|1024)', re.IGNORECASE),
        re.compile(r'(?<!\d)(1[2-7])\s+(64|128|256|512|1024)', re.IGNORECASE),
    ]:
        m = pat.search(text)
        if m:
            key = f"iphone {m.group(1)}"
            if key in MODEL_ALIASES:
                return MODEL_ALIASES[key]
    return None


def parse_message_to_offers(text: str) -> list[ParsedOffer]:
    return parse_message(text).offers
