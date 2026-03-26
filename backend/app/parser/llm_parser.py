"""
LLM-based fallback parser for complex/ambiguous price messages.

Supports any OpenAI-compatible API.
Recommended free provider: OpenRouter
  LLM_API_URL=https://openrouter.ai/api/v1
  LLM_API_KEY=<your key from https://openrouter.ai/keys>
  LLM_MODEL=google/gemma-3-27b-it:free
  LLM_FALLBACK_MODELS=meta-llama/llama-3.3-70b-instruct:free,mistralai/mistral-7b-instruct:free

On 429 / 404 the parser automatically tries each model in LLM_FALLBACK_MODELS
before giving up.
"""
import json
import logging
from typing import Optional

import httpx

from app.config import settings
from app.parser.regex_parser import ParsedOffer

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты — модуль нормализации прайсов электроники из Telegram-сообщений.

Твоя задача:
1. Проанализировать входной текст сообщения.
2. Выделить товарные позиции.
3. Для каждой позиции извлечь:
   - category
   - brand
   - model
   - memory
   - color
   - condition
   - price
   - currency
   - availability
4. Привести данные к нормализованному виду.
5. Вернуть результат строго в JSON.
6. Если уверенность низкая, установить "needs_review": true.
7. Не додумывать данные, если их нет явно.
8. Если в одном сообщении несколько позиций — вернуть массив внутри поля "items".

Правила нормализации:
- 15 pm, 15 pro max, iphone 15pm — варианты iPhone 15 Pro Max.
- 17 pro 256 — iPhone 17 Pro, 256GB.
- nat / natural — Natural Titanium, если контекст указывает на Apple Pro-модель.
- Если валюта не указана явно, пытаться определить по контексту, иначе "currency": "RUB".
- Числа рядом с моделью не считать ценой, если они похожи на объём памяти (32/64/128/256/512/1024).
- Состояние: new / used / refurbished. По умолчанию new.
- Валюта: RUB / USD / EUR.
- Память: нормализовать к формату 256GB / 1TB.
- Цвет: на английском (Black, White, Natural Titanium, Blue Titanium и т.д.).

line — продуктовая линейка: iPhone / AirPods / Apple Watch / MacBook / iPad / Mac.
category — одно из: smartphone / headphones / watch / laptop / tablet / desktop.

Пример входа: "17 pro 256"
Пример выхода:
{
  "items": [
    {
      "category": "smartphone",
      "brand": "Apple",
      "line": "iPhone",
      "model": "iPhone 17 Pro",
      "memory": "256GB",
      "color": null,
      "condition": "new",
      "sim_type": null,
      "price": null,
      "currency": "RUB",
      "availability": null,
      "confidence": 0.85,
      "needs_review": false
    }
  ]
}

Отвечай ТОЛЬКО валидным JSON, без пояснений и текста снаружи.
"""

# HTTP status codes that warrant trying the next model in the fallback chain
_RETRY_ON_CODES = {429, 404, 503, 502}


async def _call_model(client: httpx.AsyncClient, model: str, text: str) -> httpx.Response:
    """Make a single chat/completions request for the given model."""
    return await client.post(
        f"{settings.llm_api_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0.0,
            "max_tokens": 2000,
        },
    )


async def parse_with_llm(text: str) -> list[ParsedOffer]:
    """
    Parse a message using an LLM with automatic model fallback.

    Tries settings.llm_model first, then each model in
    settings.llm_fallback_models_list on 429 / 404 / 502 / 503.
    Returns a list of ParsedOffer objects, or [] on total failure.
    """
    if not settings.llm_api_key:
        logger.warning("LLM API key not configured, skipping LLM parsing")
        return []

    models_to_try = [settings.llm_model] + settings.llm_fallback_models_list

    async with httpx.AsyncClient(timeout=30.0) as client:
        for idx, model in enumerate(models_to_try):
            try:
                response = await _call_model(client, model, text)

                if response.status_code in _RETRY_ON_CODES:
                    logger.warning(
                        f"[LLM] Model {model!r} returned {response.status_code}, "
                        f"trying next fallback ..."
                    )
                    continue

                response.raise_for_status()

                if idx > 0:
                    logger.info(f"[LLM] Using fallback model: {model!r}")

                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()
                content = _extract_json(content)
                parsed = json.loads(content)

                if isinstance(parsed, dict) and "items" in parsed:
                    offers_raw = parsed["items"]
                elif isinstance(parsed, list):
                    offers_raw = parsed
                else:
                    logger.warning(f"[LLM] Unexpected structure from {model!r}: {type(parsed)}")
                    return []

                offers = [o for o in (_dict_to_parsed_offer(i) for i in offers_raw) if o]
                logger.info(f"[LLM] Parsed {len(offers)} offer(s) via {model!r}")
                return offers

            except httpx.HTTPStatusError as e:
                if e.response.status_code in _RETRY_ON_CODES:
                    logger.warning(
                        f"[LLM] Model {model!r} HTTP {e.response.status_code}, "
                        f"trying next fallback ..."
                    )
                    continue
                logger.error(
                    f"[LLM] HTTP error from {model!r}: "
                    f"{e.response.status_code} - {e.response.text[:200]}"
                )
                return []
            except json.JSONDecodeError as e:
                logger.error(f"[LLM] JSON decode error from {model!r}: {e}")
                return []
            except Exception as e:
                logger.error(f"[LLM] Unexpected error from {model!r}: {e}")
                return []

    logger.error(
        f"[LLM] All models exhausted ({len(models_to_try)} tried), giving up."
    )
    return []


def _extract_json(content: str) -> str:
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
    try:
        price = data.get("price")
        if price is not None:
            price = float(price)
        confidence = float(data.get("confidence", 0.6))
        if data.get("needs_review", False):
            confidence = min(confidence, 0.4)
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
            confidence=confidence,
            raw_line=str(data),
        )
    except Exception as e:
        logger.error(f"[LLM] Failed to convert result to ParsedOffer: {e}")
        return None
