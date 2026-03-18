"""
LLM-based fallback parser for complex/ambiguous price messages.
Uses an OpenAI-compatible API to extract structured offer data.
"""
import json
import logging
from typing import Optional

import httpx

from app.config import settings
from app.parser.regex_parser import ParsedOffer

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a specialized parser for electronics price messages from Telegram channels.
Your task is to extract structured product offers from raw text messages.

For each offer found in the message, extract:
- model: Full product model name (e.g., "iPhone 15 Pro Max", "AirPods Pro 2")
- line: Product line (e.g., "iPhone", "AirPods", "Apple Watch", "MacBook", "iPad")
- category: One of: smartphone, headphones, watch, laptop, tablet, desktop
- brand: Usually "Apple" for Apple products
- memory: Storage size (e.g., "256GB", "512GB", "1TB")
- color: Color name in English (e.g., "Natural Titanium", "Black", "Blue")
- condition: One of: new, used, refurbished
- sim_type: One of: esim, dual, or null
- price: Numeric price value (just the number)
- currency: One of: RUB, USD, EUR

Respond ONLY with a JSON array of offer objects. If you cannot parse any offers, respond with an empty array [].
Do not include any explanation or text outside the JSON.

Example input: "15 Pro Max 256 nat - 915$"
Example output: [{"model": "iPhone 15 Pro Max", "line": "iPhone", "category": "smartphone", "brand": "Apple", "memory": "256GB", "color": "Natural Titanium", "condition": "new", "sim_type": null, "price": 915, "currency": "USD"}]

Example input: "AirPods Pro 2 USB-C 14500"
Example output: [{"model": "AirPods Pro 2 USB-C", "line": "AirPods", "category": "headphones", "brand": "Apple", "memory": null, "color": null, "condition": "new", "sim_type": null, "price": 14500, "currency": "RUB"}]
"""


async def parse_with_llm(text: str) -> list[ParsedOffer]:
    """
    Parse a message using an LLM.
    Returns a list of ParsedOffer objects.
    Falls back to empty list on any error.
    """
    if not settings.llm_api_key:
        logger.warning("LLM API key not configured, skipping LLM parsing")
        return []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.llm_api_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
            )
            response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()

        # Extract JSON from response (handle markdown code blocks)
        content = _extract_json(content)

        offers_raw = json.loads(content)
        if not isinstance(offers_raw, list):
            logger.warning(f"LLM returned non-list: {type(offers_raw)}")
            return []

        offers = []
        for item in offers_raw:
            offer = _dict_to_parsed_offer(item)
            if offer:
                offers.append(offer)

        logger.info(f"LLM parsed {len(offers)} offers from message")
        return offers

    except httpx.HTTPStatusError as e:
        logger.error(f"LLM API HTTP error: {e.response.status_code} - {e.response.text[:200]}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"LLM parsing error: {e}")
        return []


def _extract_json(content: str) -> str:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Remove markdown code fences
    if "```json" in content:
        start = content.index("```json") + 7
        end = content.index("```", start)
        return content[start:end].strip()
    if "```" in content:
        start = content.index("```") + 3
        end = content.index("```", start)
        return content[start:end].strip()
    return content


def _dict_to_parsed_offer(data: dict) -> Optional[ParsedOffer]:
    """Convert a dictionary to a ParsedOffer."""
    try:
        price = data.get("price")
        if price is not None:
            price = float(price)

        return ParsedOffer(
            model=data.get("model"),
            line=data.get("line"),
            category=data.get("category"),
            brand=data.get("brand", "Apple"),
            memory=data.get("memory"),
            color=data.get("color"),
            condition=data.get("condition", "new"),
            sim_type=data.get("sim_type"),
            price=price,
            currency=data.get("currency", "RUB"),
            confidence=0.6,  # LLM results get moderate confidence
            raw_line=str(data),
        )
    except Exception as e:
        logger.error(f"Failed to convert LLM result to ParsedOffer: {e}")
        return None
