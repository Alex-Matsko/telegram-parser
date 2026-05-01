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
  "**17 Pro Max 256 Blue (eSim) - 107200 **"
  "iPad 11 128GB Blue - 28400"
  "iPhone 13 128GB Pink - 47700"
  "17 pro 256 blue eSIM -1 93,500"     <- qty before price
  "16 256 black 62700`"                <- backtick artifact
  "17 256 Black Sim+eSim 61700"        <- price at end, no dash
  "13100.00 ₽"                         <- kopeck format
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
# Delivery/speed emoji that appear after prices (🛩️ 🏎️ 🚘)
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
    # Thousand separator with dot: 62.000 or 96.500
    if re.match(r'^\d{1,3}(?:\.\d{3})+$', s):
        return s.replace('.', '')
    # Thousand separator with comma: 62,000
    if re.match(r'^\d{1,3}(?:,\d{3})+$', s):
        return s.replace(',', '')
    # Kopeck / decimal format: 13100.00 or 13100,00 — strip fractional part
    if re.match(r'^\d{4,7}[.,]\d{2}$', s):
        return re.sub(r'[.,]\d{2}$', '', s)
    # Everything else — remove separators
    return s.replace('.', '').replace(',', '')


# ---------------------------------------------------------------------------
# Quantity-before-price preprocessor
# Handles: "17 pro 256 blue eSIM -1 93,500" → "17 pro 256 blue eSIM - 93,500"
# ---------------------------------------------------------------------------

_QTY_BEFORE_PRICE = re.compile(
    r'([—\-])\s*\d{1,2}\s+(\d{2,3}[.,]\d{3}|\d{5,6})',
    re.IGNORECASE,
)


def _remove_qty_prefix(text: str) -> str:
    """Remove quantity like -1, -3 before price: '-1 93,500' → '- 93,500'"""
    return _QTY_BEFORE_PRICE.sub(r'\1 \2', text)


# ---------------------------------------------------------------------------
# Price patterns (priority order)
# ---------------------------------------------------------------------------

_PRICE_AFTER_DASH = re.compile(
    r'(?:^|\s)[—\-]\s*'
    r'(\d{1,3}(?:[.,]\d{3})*(?:\s\d{3})*\d*)'
    r'\*?'
    r'\s*(\$|€|₽|usd|eur|rub|руб|долл)?'
    r'(?=[^\d]|$)',
    re.IGNORECASE | re.UNICODE,
)

_PRICE_EXPLICIT_AFTER = re.compile(
    r'(?<!\d)(\d{1,3}(?:[.,]\d{3})*|\d{4,7})\s*(\$|€|₽|usd|eur|rub|руб|долл)(?:\b|$)',
    re.IGNORECASE,
)

_PRICE_EXPLICIT_BEFORE = re.compile(
    r'(\$|€|₽)\s*(\d{1,3}(?:[.,]\d{3})*|\d{4,7})',
    re.IGNORECASE,
)

_PRICE_SPACED = re.compile(
    r'(?<!\d)(\d{2,3}\s\d{3})(?:\b|$)',
)

# Last-resort: 5-6 digit number at end of line (no dash, no currency symbol)
# Used for formats like "17 256 Black Sim+eSim 61700" or "Air 13 Midnight 84500"
_PRICE_TRAILING = re.compile(
    r'(?<!\d)(\d{5,6})\s*$',
)

_MEMORY_PATTERN = re.compile(
    r'(?<![.\d])\b(32|64|128|256|512|1024)\s*(?:gb|гб)?\b(?!\s*(?:\$|€|₽|usd|eur|rub|руб))'
    r'|(1|2)\s*(?:tb|тб)',
    re.IGNORECASE,
)

_RAM_STORAGE_PATTERN = re.compile(
    r'\b\d{1,3}/(?:1tb|2tb|\d{2,4})\b',
    re.IGNORECASE,
)

# RAM standalone pattern: "12GB", "16GB", "32GB" — to exclude from price/storage
_RAM_STANDALONE_PATTERN = re.compile(
    r'\b(8|12|16|24|32|48|64)\s*gb\b',
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
    re.compile(r'^[-=_*~.➖]{3,}$'),
    re.compile(r'^[*_]{1,3}[^*_].{0,80}[*_]{1,3}\s*$'),
    re.compile(r'https?://', re.IGNORECASE),
    re.compile(r'\+7[\s\-]?\(?\d{3}\)?'),
    re.compile(r'\b8[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}'),
    re.compile(r'^[78]\d{10}$'),                          # bare phone: 89231636383
    re.compile(r'(?:нажмите|кнопку|прайс открыт|прайс закрыт)', re.IGNORECASE),
    re.compile(r'^[+]{1,3}$'),                            # single reaction: +, ++, +++
    re.compile(r'^(?:👍|✅|👌|🤝|💯)\s*$', re.UNICODE),  # emoji reactions
    re.compile(r'заказ\s*:\s*#', re.IGNORECASE),         # order template: Заказ: #xxx
    re.compile(r'принят в обработку', re.IGNORECASE),    # order template
    re.compile(r'общая стоимость', re.IGNORECASE),       # order total line
]

_NOISE_STARTS = [
    "прайс", "price list", "обновлен", "updated", "дата",
    "актуальный", "актуально", "на ", "от ", "#",
    "⬇️", "👇", "доставка", "оплата", "гарантия",
    "warranty", "контакты", "цены в канале", "t.me",
    "уважаемые", "хотим донести", "как вы знаете",  # info paragraphs
    "добрый день", "добрый вечер", "доброе утро",
]

_CHAT_KEYWORDS = [
    "привет", "даров", "как дают", "как пишут", "да?", "есть?",
    "hello", "hi ", "hey ", "thanks", "спасиб", "бро",
    "спусти", "закинешь", "отложи", "сделаем", "пожалуйста",
]

_PRICE_SIGNAL = re.compile(
    r'\d{4,7}'
    r'|\d{2,3}[.,]\d{3}'
    r'|\d{2,3}\s\d{3}'
    r'|\$|€|₽|\busd\b|\beur\b|\bруб\b',
    re.IGNORECASE,
)

_SYSTEM_MESSAGE_PATTERNS = re.compile(
    r'^(?:прайс|price)\s*[!.]?$'
    r'|прайс\s+(?:открыт|закрыт)'
    r'|нажмите\s+кнопку'
    r'|кнопку\s+.{0,30}чтобы'
    r'|возвращайтесь\s+завтра'
    r'|список\s+товаров'
    r'|показать\s+товары'
    r'|обновить\s+список',
    re.IGNORECASE | re.UNICODE,
)

# Long info paragraph: >120 chars, no price separator dash
_LONG_INFO_PARAGRAPH = re.compile(r'^.{120,}$')
_HAS_PRICE_SEPARATOR = re.compile(r'[—\-]\s*\d{4,6}')


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
        parts = re.split(r'[;|]', line)
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
    # Long info paragraph without a price separator is not a product line
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
    # Remove quantity prefix before price: "-1 93,500" → "- 93,500"
    text = _remove_qty_prefix(line)

    model_info, model_span = _extract_model_with_span(text)
    # remaining = text with model name cut out
    # Used for both memory extraction AND price extraction
    # to prevent "iPhone 16" + "256" concatenating into price 16256
    remaining = text
    if model_info:
        offer.line, offer.model, offer.category = model_info
        offer.brand = _resolve_brand(offer.line)
        offer.confidence += 0.4
        if model_span:
            remaining = (text[:model_span[0]] + " " + text[model_span[1]:]).strip()

    # KEY FIX: extract price from remaining (model stripped), not full text
    price_val, currency, _ = _extract_price(remaining)
    if price_val is not None:
        offer.price = price_val
        offer.currency = currency

    memory = _extract_memory(remaining)
    if memory:
        offer.memory = memory
        offer.confidence += 0.2

    # Color/condition/sim still use full text for broader context
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
    excluded: set[str] = set()

    for m in _MEMORY_PATTERN.finditer(text):
        excluded.add(re.sub(r'[^\d]', '', m.group(0)))

    for m in _RAM_STORAGE_PATTERN.finditer(text):
        for part in re.split(r'/', m.group(0).lower()):
            excluded.add(re.sub(r'[^\d]', '', part))

    # Exclude RAM values (8GB, 16GB, 24GB, 32GB) — common in Mac specs
    for m in _RAM_STANDALONE_PATTERN.finditer(text):
        excluded.add(re.sub(r'[^\d]', '', m.group(0)))

    def _try_parse(num_str: str, curr_raw: str) -> Optional[tuple[float, str]]:
        normalized = _normalize_price_str(num_str)
        if normalized in excluded:
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

    for m in _PRICE_SPACED.finditer(text):
        result = _try_parse(m.group(1), "")
        if result and result[0] >= _PRICE_MIN:
            return result[0], result[1], (m.start(), m.end())

    # Last resort: 5-6 digit number at end of line
    # Handles: "Air 13 Midnight 84500", "17 256 Black Sim+eSim 61700"
    m = _PRICE_TRAILING.search(text)
    if m:
        result = _try_parse(m.group(1), "")
        if result:
            return result[0], result[1], (m.start(), m.end())

    return None, "RUB", None


def _resolve_currency(s: str) -> str:
    return CURRENCY_ALIASES.get(s.strip().lower(), "RUB")


def _extract_model_with_span(text: str) -> tuple[Optional[tuple[str, str, str]], Optional[tuple[int, int]]]:
    lower = text.lower()
    normalized = re.sub(r'[/\-|•·]', ' ', lower)
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
    This avoids picking RAM (8GB/16GB) instead of storage (256GB/512GB)
    in Mac spec strings like 'M4 16GB 256GB 2025'.
    """
    best_raw: Optional[str] = None
    best_val: int = 0

    for m in _MEMORY_PATTERN.finditer(text):
        if m.group(1):
            raw = m.group(1)
            val = int(raw)
        else:
            raw = m.group(2) + "tb"
            val = int(m.group(2)) * 1024  # 1TB=1024, 2TB=2048

        # Skip known RAM sizes (8/12/16/24/32 without explicit GB marker)
        # Only skip if explicitly tagged as RAM by _RAM_STANDALONE_PATTERN
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
    color_text = re.sub(r'\d+', ' ', lower)
    color_text = re.sub(r'[/\-|•·()]', ' ', color_text)
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
