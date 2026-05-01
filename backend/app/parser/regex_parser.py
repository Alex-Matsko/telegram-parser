"""
Rule-based extraction of product offers from price message text.

Supported price formats:
  "Galaxy S26 Ultra 12/512 Jetblack - 94500"
  "17 Pro 256 Blue eSim \U0001f1ef\U0001f1f5 - 96.500*"
  "15 Pro Max 256 nat - 915$"
  "iPhone 15 PM 256 Natural 91 500"
  "16/256 black esim 101000"
  "AirPods Pro 2 USB-C 14500"
  "Canon G7 X Mark III Silver - 88000"
  "**17 Pro Max 256 Blue (eSim) - 107200 **"
  "iPad 11 128GB Blue - 28400"
  "iPhone 13 128GB Pink - 47700"
  "17 pro 256 blue eSIM -1 93,500"     <- qty before price
  "16 256 black 62700`"                <- backtick artifact
  "17 256 Black Sim+eSim 61700"        <- price at end, no dash
  "13100.00 \u20bd"                         <- kopeck format
  "16 256 Black - 62700"               <- price AFTER dash separator only
  "S25 Ultra 12/512 Phantom Black - 94000"  <- Samsung RAM/storage
  "MacBook Air 13 M4 16GB 256GB - 84500"    <- Mac RAM vs storage
  "Galaxy S26 Ultra 1TB Silver - 89000"     <- 1TB as memory
  "16 | 256 | Black | 62700"           <- pipe-delimited table row
  "\u041c\u043e\u0434\u0435\u043b\u044c\t\u041f\u0430\u043c\u044f\u0442\u044c\t\u0426\u0435\u043d\u0430"           <- tab-separated table format
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

_PRICE_MIN = 1000


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
# Markdown / emoji stripper
# ---------------------------------------------------------------------------

_MD_BOLD_ITALIC = re.compile(r'[*_`]{1,3}')
_EMOJI_FLAGS = re.compile(r'[\U0001F1E0-\U0001F1FF]{2}', re.UNICODE)
_DELIVERY_EMOJI = re.compile(
    r'[\U0001F6E9\U0001F3CE\U0001F698\U0001F697\U0001F6FB\U0001F69A\u2708\u2702]'
    r'[\uFE0F\u20E3]?',
    re.UNICODE,
)


def _strip_markdown(text: str) -> str:
    text = _MD_BOLD_ITALIC.sub('', text)
    text = _EMOJI_FLAGS.sub('', text)
    text = _DELIVERY_EMOJI.sub('', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


# ---------------------------------------------------------------------------
# Price helpers
# ---------------------------------------------------------------------------

def _normalize_price_str(s: str) -> str:
    s = re.sub(r'[^\d.,]', '', s)
    if re.match(r'^\d{1,3}(?:\.\d{3})+$', s):
        return s.replace('.', '')
    if re.match(r'^\d{1,3}(?:,\d{3})+$', s):
        return s.replace(',', '')
    if re.match(r'^\d{4,7}[.,]\d{2}$', s):
        return re.sub(r'[.,]\d{2}$', '', s)
    return s.replace('.', '').replace(',', '')


# ---------------------------------------------------------------------------
# Quantity-before-price preprocessor
# ---------------------------------------------------------------------------

_QTY_BEFORE_PRICE = re.compile(
    r'([\u2014\-])\s*\d{1,2}\s+(\d{2,3}[.,]\d{3}|\d{5,6})',
    re.IGNORECASE,
)


def _remove_qty_prefix(text: str) -> str:
    return _QTY_BEFORE_PRICE.sub(r'\1 \2', text)


# ---------------------------------------------------------------------------
# Price zone splitter
#
# Supports three formats:
#   1. Dash/em-dash separator: "16 256 Black - 62700"  -> price_zone = "62700"
#   2. Pipe chain (table row): "16 | 256 | Black | 62700" -> price_zone = "62700"
#      (last pipe segment that contains a price-like number)
#   3. No separator: "17 256 Black 61700" -> price_zone = full text
# ---------------------------------------------------------------------------

_PRICE_ZONE_SEPARATOR = re.compile(r'\s*[\u2014\-]\s*')
_PIPE_SEPARATOR = re.compile(r'\s*\|\s*')
_LOOKS_LIKE_PRICE = re.compile(r'\b\d{4,7}\b|\b\d{1,3}[.,]\d{3}\b|\b\d{2,3}\s\d{3}\b')


def _get_price_zone(text: str) -> str:
    """
    Return the substring most likely containing the price.

    Strategy (in priority order):
    1. Pipe-delimited row: take the LAST pipe-segment that looks like a price.
       e.g. "16 | 256 | Black | 62700" -> "62700"
       e.g. "16 | 256 | Black | esim | 62700" -> "62700"
    2. Dash/em-dash separator: take everything to the RIGHT.
       e.g. "16 256 Black - 62700" -> "62700"
    3. Fallback: return full text (price is at the end).
    """
    # Strategy 1: pipe-delimited
    if '|' in text:
        parts = _PIPE_SEPARATOR.split(text)
        # Walk from the right, find first segment with a price-like number
        for seg in reversed(parts):
            seg = seg.strip()
            if _LOOKS_LIKE_PRICE.search(seg):
                return seg
        # No price-looking segment found -> fall through

    # Strategy 2: dash separator
    parts = _PRICE_ZONE_SEPARATOR.split(text, maxsplit=1)
    if len(parts) == 2 and parts[1].strip():
        return parts[1].strip()

    # Strategy 3: full text
    return text


# ---------------------------------------------------------------------------
# Price patterns (priority order)
# ---------------------------------------------------------------------------

_PRICE_AFTER_DASH = re.compile(
    r'(?:^|\s)[\u2014\-]\s*'
    r'(\d{1,3}(?:[.,]\d{3})*(?:\s\d{3})*\d*)'
    r'\*?'
    r'\s*(\$|\u20ac|\u20bd|usd|eur|rub|\u0440\u0443\u0431|\u0434\u043e\u043b\u043b)?'
    r'(?=[^\d]|$)',
    re.IGNORECASE | re.UNICODE,
)

_PRICE_EXPLICIT_AFTER = re.compile(
    r'(?<!\d)(\d{1,3}(?:[.,]\d{3})*|\d{4,7})\s*(\$|\u20ac|\u20bd|usd|eur|rub|\u0440\u0443\u0431|\u0434\u043e\u043b\u043b)(?:\b|$)',
    re.IGNORECASE,
)

_PRICE_EXPLICIT_BEFORE = re.compile(
    r'(\$|\u20ac|\u20bd)\s*(\d{1,3}(?:[.,]\d{3})*|\d{4,7})',
    re.IGNORECASE,
)

# Scoped to price_zone only — never runs on left side of separator.
# Tightened: require at least one digit group after space, add end-of-token lookahead.
_PRICE_SPACED = re.compile(
    r'(?<!\d)(\d{2,3}\s\d{3})(?=\s|[^\d]|$)',
)

# Last-resort: 5-6 digit number at end of price_zone
_PRICE_TRAILING = re.compile(
    r'(?<!\d)(\d{5,6})\s*[`\*]?\s*$',
)

# Standard storage values (GB) — these numbers are NEVER prices
_STORAGE_VALUES: frozenset[str] = frozenset({'32', '64', '128', '256', '512', '1024', '2048'})

_MEMORY_PATTERN = re.compile(
    r'(?<![.\d])\b(32|64|128|256|512|1024)\s*(?:gb|\u0433\u0431)?\b(?!\s*(?:\$|\u20ac|\u20bd|usd|eur|rub|\u0440\u0443\u0431))'
    r'|(1|2)\s*(?:tb|\u0442\u0431)',
    re.IGNORECASE,
)

_RAM_STORAGE_PATTERN = re.compile(
    r'\b\d{1,3}/(?:1tb|2tb|\d{2,4})\b',
    re.IGNORECASE,
)

_RAM_STANDALONE_PATTERN = re.compile(
    r'\b(8|12|16|24|32|48|64)\s*gb\b',
    re.IGNORECASE,
)

_MODEL_NUMBER_PATTERN = re.compile(
    r'(?:^|(?<=\s))(?:iphone\s*)?(1[0-9]|[2-9])(?=\s|$|[/\-])',
    re.IGNORECASE,
)

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
    re.compile(r'^[-=_*~.\u2796]{3,}$'),
    re.compile(r'^[*_]{1,3}[^*_].{0,80}[*_]{1,3}\s*$'),
    re.compile(r'https?://', re.IGNORECASE),
    re.compile(r'\+7[\s\-]?\(?\d{3}\)?'),
    re.compile(r'\b8[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}'),
    re.compile(r'^[78]\d{10}$'),
    re.compile(r'(?:\u043d\u0430\u0436\u043c\u0438\u0442\u0435|\u043a\u043d\u043e\u043f\u043a\u0443|\u043f\u0440\u0430\u0439\u0441 \u043e\u0442\u043a\u0440\u044b\u0442|\u043f\u0440\u0430\u0439\u0441 \u0437\u0430\u043a\u0440\u044b\u0442)', re.IGNORECASE),
    re.compile(r'^[+]{1,3}$'),
    re.compile(r'^(?:\U0001f44d|\u2705|\U0001f44c|\U0001f91d|\U0001f4af)\s*$', re.UNICODE),
    re.compile(r'\u0437\u0430\u043a\u0430\u0437\s*:\s*#', re.IGNORECASE),
    re.compile(r'\u043f\u0440\u0438\u043d\u044f\u0442 \u0432 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0443', re.IGNORECASE),
    re.compile(r'\u043e\u0431\u0449\u0430\u044f \u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c', re.IGNORECASE),
    # Table header lines: "Модель | Память | Цена" or "Модель\tПамять\tЦена" (no digits at all)
    re.compile(r'^[^\d]+(?:\||\t)[^\d]+(?:\||\t)[^\d]+$'),
]

_NOISE_STARTS = [
    "\u043f\u0440\u0430\u0439\u0441", "price list", "\u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d", "updated", "\u0434\u0430\u0442\u0430",
    "\u0430\u043a\u0442\u0443\u0430\u043b\u044c\u043d\u044b\u0439", "\u0430\u043a\u0442\u0443\u0430\u043b\u044c\u043d\u043e", "\u043d\u0430 ", "\u043e\u0442 ", "#",
    "\u2b07\ufe0f", "\U0001f447", "\u0434\u043e\u0441\u0442\u0430\u0432\u043a\u0430", "\u043e\u043f\u043b\u0430\u0442\u0430", "\u0433\u0430\u0440\u0430\u043d\u0442\u0438\u044f",
    "warranty", "\u043a\u043e\u043d\u0442\u0430\u043a\u0442\u044b", "\u0446\u0435\u043d\u044b \u0432 \u043a\u0430\u043d\u0430\u043b\u0435", "t.me",
    "\u0443\u0432\u0430\u0436\u0430\u0435\u043c\u044b\u0435", "\u0445\u043e\u0442\u0438\u043c \u0434\u043e\u043d\u0435\u0441\u0442\u0438", "\u043a\u0430\u043a \u0432\u044b \u0437\u043d\u0430\u0435\u0442\u0435",
    "\u0434\u043e\u0431\u0440\u044b\u0439 \u0434\u0435\u043d\u044c", "\u0434\u043e\u0431\u0440\u044b\u0439 \u0432\u0435\u0447\u0435\u0440", "\u0434\u043e\u0431\u0440\u043e\u0435 \u0443\u0442\u0440\u043e",
]

_CHAT_KEYWORDS = [
    "\u043f\u0440\u0438\u0432\u0435\u0442", "\u0434\u0430\u0440\u043e\u0432", "\u043a\u0430\u043a \u0434\u0430\u044e\u0442", "\u043a\u0430\u043a \u043f\u0438\u0448\u0443\u0442", "\u0434\u0430?", "\u0435\u0441\u0442\u044c?",
    "hello", "hi ", "hey ", "thanks", "\u0441\u043f\u0430\u0441\u0438\u0431", "\u0431\u0440\u043e",
    "\u0441\u043f\u0443\u0441\u0442\u0438", "\u0437\u0430\u043a\u0438\u043d\u0435\u0448\u044c", "\u043e\u0442\u043b\u043e\u0436\u0438", "\u0441\u0434\u0435\u043b\u0430\u0435\u043c", "\u043f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430",
]

_PRICE_SIGNAL = re.compile(
    r'\d{4,7}'
    r'|\d{2,3}[.,]\d{3}'
    r'|\d{2,3}\s\d{3}'
    r'|\$|\u20ac|\u20bd|\busd\b|\beur\b|\b\u0440\u0443\u0431\b',
    re.IGNORECASE,
)

_SYSTEM_MESSAGE_PATTERNS = re.compile(
    r'^(?:\u043f\u0440\u0430\u0439\u0441|price)\s*[!.]?$'
    r'|\u043f\u0440\u0430\u0439\u0441\s+(?:\u043e\u0442\u043a\u0440\u044b\u0442|\u0437\u0430\u043a\u0440\u044b\u0442)'
    r'|\u043d\u0430\u0436\u043c\u0438\u0442\u0435\s+\u043a\u043d\u043e\u043f\u043a\u0443'
    r'|\u043a\u043d\u043e\u043f\u043a\u0443\s+.{0,30}\u0447\u0442\u043e\u0431\u044b'
    r'|\u0432\u043e\u0437\u0432\u0440\u0430\u0449\u0430\u0439\u0442\u0435\u0441\u044c\s+\u0437\u0430\u0432\u0442\u0440\u0430'
    r'|\u0441\u043f\u0438\u0441\u043e\u043a\s+\u0442\u043e\u0432\u0430\u0440\u043e\u0432'
    r'|\u043f\u043e\u043a\u0430\u0437\u0430\u0442\u044c\s+\u0442\u043e\u0432\u0430\u0440\u044b'
    r'|\u043e\u0431\u043d\u043e\u0432\u0438\u0442\u044c\s+\u0441\u043f\u0438\u0441\u043e\u043a',
    re.IGNORECASE | re.UNICODE,
)

_LONG_INFO_PARAGRAPH = re.compile(r'^.{120,}$')
_HAS_PRICE_SEPARATOR = re.compile(r'[\u2014\-]\s*\d{4,6}')


def is_obviously_not_price_message(text: str) -> bool:
    if not text or not text.strip():
        return True
    stripped = text.strip()
    if _SYSTEM_MESSAGE_PATTERNS.search(stripped):
        return True
    if len(stripped) < 6 and not any(c.isdigit() for c in stripped):
        return True
    if not _PRICE_SIGNAL.search(stripped):
        return True
    return False


def parse_message(text: str) -> ParseResult:
    result = ParseResult()
    lines = _split_into_lines(text)
    for line in lines:
        stripped = line.strip()
        if not stripped or len(stripped) < 3:
            continue
        if _is_noise_line(stripped):
            continue
        clean = _strip_markdown(stripped)
        if not clean or len(clean) < 3:
            continue
        offer = _parse_single_line(clean)
        if offer and offer.model and offer.price and offer.price >= _PRICE_MIN:
            offer.raw_line = stripped
            result.offers.append(offer)
        elif clean and len(clean) > 5:
            result.unparsed_lines.append(clean)
    return result


def _split_into_lines(text: str) -> list[str]:
    lines = text.split("\n")
    expanded = []
    for line in lines:
        # Also split on semicolons for semicolon-delimited lists
        parts = re.split(r'[;]', line)
        expanded.extend(parts)
    return expanded


def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    lower = stripped.lower()
    for pat in _NOISE_PATTERNS:
        if pat.search(stripped):
            return True
    clean = _strip_markdown(stripped)
    if not any(c.isdigit() for c in clean):
        return True
    if _LONG_INFO_PARAGRAPH.match(stripped) and not _HAS_PRICE_SEPARATOR.search(stripped):
        return True
    for ns in _NOISE_STARTS:
        if lower.startswith(ns):
            return True
    if len(stripped) < 60:
        for kw in _CHAT_KEYWORDS:
            if kw in lower:
                return True
    return False


def _parse_single_line(line: str) -> Optional[ParsedOffer]:
    offer = ParsedOffer()
    text = _remove_qty_prefix(line)

    model_info, model_span = _extract_model_with_span(text)
    remaining = text
    if model_info:
        offer.line, offer.model, offer.category = model_info
        offer.brand = _resolve_brand(offer.line)
        offer.confidence += 0.4
        if model_span:
            remaining = (text[:model_span[0]] + " " + text[model_span[1]:]).strip()

    price_val, currency, _ = _extract_price(remaining)
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
    """
    Extract price from text.

    Blacklist strategy (numbers that are NEVER prices):
      1. All standard storage values (32/64/128/256/512/1024/2048)
      2. RAM/storage slash format: X/Y -> both X and Y excluded
      3. RAM standalone: 8GB, 12GB, 16GB etc.
      4. Model generation numbers: "16" in "iPhone 16"

    Price zone strategy:
      - Pipe-delimited row -> last pipe-segment with a price-like number
      - Dash/em-dash separator -> everything to the RIGHT
      - No separator -> full text (price expected at end)

    Anti-ambiguity guards:
      - _PRICE_SPACED is scoped to price_zone only
      - Spaced price candidate where first segment is a storage value is rejected
        e.g. "256 627" in price_zone="256 62700" -> rejected because 256 \u2208 storage
      - Spaced price result must be >= 10000 (prevents 1 000 ghost prices)
    """
    excluded: set[str] = set()
    excluded.update(_STORAGE_VALUES)

    for m in _MEMORY_PATTERN.finditer(text):
        excluded.add(re.sub(r'[^\d]', '', m.group(0)))

    for m in _RAM_STORAGE_PATTERN.finditer(text):
        for part in re.split(r'/', m.group(0).lower()):
            excluded.add(re.sub(r'[^\d]', '', part))

    for m in _RAM_STANDALONE_PATTERN.finditer(text):
        excluded.add(re.sub(r'[^\d]', '', m.group(0)))

    for m in _MODEL_NUMBER_PATTERN.finditer(text):
        excluded.add(m.group(1))

    def _try_parse(num_str: str, curr_raw: str) -> Optional[tuple[float, str]]:
        normalized = _normalize_price_str(num_str)
        if normalized in excluded:
            return None
        if normalized in _STORAGE_VALUES:
            return None
        try:
            val = float(normalized)
        except ValueError:
            return None
        currency = _resolve_currency(curr_raw) if curr_raw else "RUB"
        min_val = 100 if currency in ("USD", "EUR") else _PRICE_MIN
        if val < min_val:
            return None
        return val, currency

    # Priority 1: explicit dash/currency patterns on full text
    for m in _PRICE_AFTER_DASH.finditer(text):
        result = _try_parse(m.group(1), (m.group(2) or "").lower())
        if result:
            return result[0], result[1], (m.start(), m.end())

    for m in _PRICE_EXPLICIT_AFTER.finditer(text):
        result = _try_parse(m.group(1), m.group(2).lower())
        if result:
            return result[0], result[1], (m.start(), m.end())

    for m in _PRICE_EXPLICIT_BEFORE.finditer(text):
        result = _try_parse(m.group(2), m.group(1).lower())
        if result:
            return result[0], result[1], (m.start(), m.end())

    # Priority 2: spaced price & trailing — scoped to price_zone ONLY
    price_zone = _get_price_zone(text)

    for m in _PRICE_SPACED.finditer(price_zone):
        raw = m.group(1)              # e.g. "256 627" or "62 700"
        left_part = raw.split()[0]    # e.g. "256" or "62"
        # Guard: reject if left part is a known storage value (256, 512, etc.)
        if left_part in _STORAGE_VALUES:
            continue
        result = _try_parse(raw, "")
        # Guard: spaced prices must be >= 10000 to avoid ghost small prices
        if result and result[0] >= 10000:
            return result[0], result[1], (m.start(), m.end())

    # Last resort: 5-6 digit number at end of price_zone
    m = _PRICE_TRAILING.search(price_zone)
    if m:
        result = _try_parse(m.group(1), "")
        if result:
            return result[0], result[1], (m.start(), m.end())

    return None, "RUB", None


def _resolve_currency(s: str) -> str:
    return CURRENCY_ALIASES.get(s.strip().lower(), "RUB")


def _extract_model_with_span(text: str) -> tuple[Optional[tuple[str, str, str]], Optional[tuple[int, int]]]:
    lower = text.lower()
    normalized = re.sub(r'[/\-|\u2022\u00b7]', ' ', lower)
    normalized = re.sub(r'\s+', ' ', normalized).strip()

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
    """
    Extract storage memory, preferring the largest value found.
    Skips standalone RAM values (8/12/16/24/32 GB without explicit context).
    In Mac spec strings like 'M4 16GB 256GB', picks 256GB (storage) over 16GB (RAM).
    """
    best_raw: Optional[str] = None
    best_val: int = 0

    for m in _MEMORY_PATTERN.finditer(text):
        if m.group(1):
            raw = m.group(1)
            val = int(raw)
        else:
            raw = m.group(2) + "tb"
            val = int(m.group(2)) * 1024

        if _RAM_STANDALONE_PATTERN.match(m.group(0).strip()):
            continue

        if val > best_val:
            best_val = val
            best_raw = raw

    if best_raw is None:
        return None
    if best_raw.endswith("tb"):
        tb_num = best_raw[:-2]
        return MEMORY_ALIASES.get(best_raw, f"{tb_num}TB")
    return MEMORY_ALIASES.get(best_raw.lower(), best_raw.upper() + "GB")


def _extract_color(text: str) -> Optional[str]:
    lower = text.lower()
    left_side = _PRICE_ZONE_SEPARATOR.split(lower, maxsplit=1)[0]
    color_text = re.sub(r'\d+', ' ', left_side)
    color_text = re.sub(r'[/\-|\u2022\u00b7()]', ' ', color_text)
    color_text = re.sub(r'\s+', ' ', color_text).strip()
    color_text_full = re.sub(r'\d+', ' ', lower)
    color_text_full = re.sub(r'[/\-|\u2022\u00b7()]', ' ', color_text_full)
    color_text_full = re.sub(r'\s+', ' ', color_text_full).strip()
    sorted_colors = sorted(COLOR_ALIASES.keys(), key=len, reverse=True)
    for alias in sorted_colors:
        pat = r'(?:^|(?<=\s))' + re.escape(alias) + r'(?=\s|$)'
        if re.search(pat, color_text) or re.search(pat, color_text_full):
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
