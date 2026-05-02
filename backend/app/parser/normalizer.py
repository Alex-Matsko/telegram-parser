"""
SKU normalization and product catalog matching.

Takes parsed offer data, normalizes to a canonical SKU format,
and matches or creates entries in the product catalog.
"""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from thefuzz import fuzz

from app.config import settings
from app.models.product_catalog import ProductCatalog
from app.parser.regex_parser import ParsedOffer

logger = logging.getLogger(__name__)

# Maximum number of catalog entries loaded into memory for fuzzy matching.
# Prevents OOM as the product catalog grows.
_FUZZY_CANDIDATE_LIMIT = 500


def build_sku_key(
    category: str,
    brand: str,
    model: str,
    memory: Optional[str] = None,
    color: Optional[str] = None,
    condition: str = "new",
    sim_type: Optional[str] = None,
) -> str:
    """
    Build a normalized SKU key.
    Format: {category}/{brand}/{model}/{memory}/{color}/{condition}[/{sim_type}]
    """
    parts = [
        _norm(category),
        _norm(brand),
        _norm(model),
        _norm(memory) if memory else "_",
        _norm(color) if color else "_",
        _norm(condition),
    ]
    if sim_type:
        parts.append(_norm(sim_type))
    return "/".join(parts)


def build_normalized_name(
    model: str,
    memory: Optional[str] = None,
    color: Optional[str] = None,
    condition: str = "new",
    sim_type: Optional[str] = None,
) -> str:
    """Build a human-readable normalized product name."""
    parts = [model]
    if memory:
        parts.append(memory)
    if color:
        parts.append(color)
    if sim_type:
        parts.append(sim_type.upper())
    if condition != "new":
        parts.append(f"({condition})")
    return " ".join(parts)


def _norm(s: str) -> str:
    """Normalize a string for SKU key: lowercase, strip, replace spaces."""
    return s.strip().lower().replace(" ", "-") if s else "_"


async def normalize_and_match(
    offer: ParsedOffer,
    session: AsyncSession,
) -> tuple[Optional[ProductCatalog], float]:
    """
    Normalize a parsed offer and match/create a product catalog entry.

    Returns (product, confidence) where product is the matched/created
    catalog entry, or None if confidence is too low.
    """
    if not offer.model:
        return None, 0.0

    sku_key = build_sku_key(
        category=offer.category or "unknown",
        brand=offer.brand,
        model=offer.model,
        memory=offer.memory,
        color=offer.color,
        condition=offer.condition,
        sim_type=offer.sim_type,
    )

    # 1. Try exact SKU match
    result = await session.execute(
        select(ProductCatalog).where(ProductCatalog.sku_key == sku_key)
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.debug(f"Exact SKU match: {sku_key}")
        return existing, 1.0

    # 2. Try fuzzy match against existing products (capped at _FUZZY_CANDIDATE_LIMIT)
    fuzzy_match, fuzzy_score = await _fuzzy_match_product(offer, session)
    if fuzzy_match and fuzzy_score >= 90:
        logger.debug(
            f"Fuzzy match (score={fuzzy_score}): {sku_key} -> {fuzzy_match.sku_key}"
        )
        return fuzzy_match, fuzzy_score / 100.0

    # 3. Create new entry if confidence is sufficient
    if offer.confidence >= settings.parser_confidence_threshold:
        normalized_name = build_normalized_name(
            model=offer.model,
            memory=offer.memory,
            color=offer.color,
            condition=offer.condition,
            sim_type=offer.sim_type,
        )

        # Валидация brand перед INSERT — колонка NOT NULL в product_catalog.
        # Если LLM вернул brand=None (например для категории 'component'),
        # используем model как fallback, иначе возвращаем None чтобы не крашить сессию.
        resolved_brand = offer.brand
        if not resolved_brand:
            if offer.category == "component" and offer.model:
                resolved_brand = offer.model
                logger.warning(
                    f"Brand is None for component '{offer.model}', using model as brand fallback"
                )
            else:
                logger.warning(
                    f"Skipping product creation: brand is None for "
                    f"category='{offer.category}' model='{offer.model}'"
                )
                return None, offer.confidence

        new_product = ProductCatalog(
            category=offer.category or "unknown",
            brand=resolved_brand,
            line=offer.line,
            model=offer.model,
            memory=offer.memory,
            color=offer.color,
            sim_type=offer.sim_type,
            condition=offer.condition,
            normalized_name=normalized_name,
            sku_key=sku_key,
        )
        session.add(new_product)
        await session.flush()
        logger.info(f"Created new product: {normalized_name} (SKU: {sku_key})")
        return new_product, offer.confidence

    # 4. If we had a fuzzy match with lower score, return it with reduced confidence
    if fuzzy_match and fuzzy_score >= 70:
        return fuzzy_match, fuzzy_score / 100.0

    logger.info(f"No confident match for: {offer.model} (confidence={offer.confidence})")
    return None, offer.confidence


async def _fuzzy_match_product(
    offer: ParsedOffer,
    session: AsyncSession,
) -> tuple[Optional[ProductCatalog], int]:
    """
    Fuzzy match a parsed offer against existing products.
    Loads at most _FUZZY_CANDIDATE_LIMIT rows to prevent memory issues.
    Returns (best_match, score) where score is 0-100.
    """
    search_parts = [offer.model or ""]
    if offer.memory:
        search_parts.append(offer.memory)
    if offer.color:
        search_parts.append(offer.color)
    search_str = " ".join(search_parts).lower()

    # Query candidates: same brand + category, limited to avoid OOM
    stmt = (
        select(ProductCatalog)
        .where(ProductCatalog.brand == offer.brand)
        .limit(_FUZZY_CANDIDATE_LIMIT)
    )
    if offer.category:
        stmt = stmt.where(ProductCatalog.category == offer.category)

    result = await session.execute(stmt)
    candidates = result.scalars().all()

    if not candidates:
        return None, 0

    best_match: Optional[ProductCatalog] = None
    best_score = 0

    for product in candidates:
        candidate_str = product.normalized_name.lower()
        score = fuzz.token_sort_ratio(search_str, candidate_str)

        if offer.model and product.model and offer.model.lower() == product.model.lower():
            score = min(score + 20, 100)

        if offer.memory and product.memory and offer.memory == product.memory:
            score = min(score + 10, 100)

        if offer.condition != product.condition:
            score = max(score - 15, 0)

        if score > best_score:
            best_score = score
            best_match = product

    return best_match, best_score
