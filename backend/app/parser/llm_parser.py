"""
LLM-based fallback parser for complex/ambiguous price messages.

Recommended .env for OpenRouter free tier:
  LLM_API_URL=https://openrouter.ai/api/v1
  LLM_API_KEY=sk-or-v1-...
  LLM_MODEL=openrouter/auto
  LLM_FALLBACK_MODELS=meta-llama/llama-3.3-70b-instruct:free,mistralai/mistral-small-3.1-24b-instruct:free,nvidia/llama-3.1-nemotron-nano-8b-v1:free
  LLM_RATE_LIMIT_DELAY=1.0

`openrouter/auto` is a free meta-router that picks the best available free
model automatically — use it as primary to avoid maintaining model IDs.
"""
import asyncio
import json
import logging
from typing import Optional

import httpx

from app.config import settings
from app.parser.regex_parser import ParsedOffer

logger = logging.getLogger(__name__)

_FALLBACK_STATUS_CODES = {429, 404, 503, 502}

SYSTEM_PROMPT = """Ты — модуль нормализации прайсов электроники из Telegram-сообщений.

Твоя задача:
1. Проанализировать входной текст сообщения.
2. Выделить товарные позиции.
3. Для каждой позиции извлечь:
   - category, brand, model, memory, color, condition, price, currency, availability
4. Привести данные к нормализованному виду.
5. Вернуть результат строго в JSON.
6. Если уверенность низкая, установить "needs_review": true.
7. Не додумывать данные, если их нет явно или они не следуют надёжно из контекста.
8. Если в одном сообщении несколько позиций — вернуть массив объектов внутри поля "items".

Правила нормализации:
- 15 pm, 15 pro max, iphone 15pm — варианты iPhone 15 Pro Max.
- 17 pro 256 — iPhone 17 Pro, 256GB.
- nat / natural — Natural Titanium, если контекст указывает на Apple Pro-модель.
- Если валюта не указана, пытаться определить по контексту, иначе "currency": "RUB".
- Числа рядом с моделью не считать ценой, если они похожи на объём памяти (32/64/128/256/512/1024).
- Строки-заголовки, даты, подписи — игнорировать.
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

# Global semaphore: max concurrent LLM calls across the process.
# Free tier = 20 req/min → 1 req / 3s is safe. Adjust via LLM_CONCURRENCY in .env.
_llm_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _llm_semaphore
    if _llm_semaphore is None:
        concurrency = getattr(settings, "llm_concurrency", 1)
        _llm_semaphore = asyncio.Semaphore(concurrency)
    return _llm_semaphore


async def _call_model(client: httpx.AsyncClient, model: str, text: str) -> list[ParsedOffer]:
    """Single LLM call. Raises HTTPStatusError on non-2xx."""
    response = await client.post(
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
    response.raise_for_status()

    data = response.json()
    content = data["choices"][0]["message"]["content"].strip()
    content = _extract_json(content)
    parsed = json.loads(content)

    if isinstance(parsed, dict) and "items" in parsed:
        offers_raw = parsed["items"]
    elif isinstance(parsed, list):
        offers_raw = parsed
    else:
        logger.warning(f"LLM ({model}) unexpected structure: {type(parsed)}")
        return []

    return [o for o in (_dict_to_parsed_offer(i) for i in offers_raw) if o]


async def parse_with_llm(text: str) -> list[ParsedOffer]:
    """
    Parse a message using LLM with automatic model fallback.

    Concurrency is limited by a global semaphore (default 1 = sequential)
    to avoid hitting the free-tier rate limit when parsing a large batch.
    Add a small inter-call delay via LLM_RATE_LIMIT_DELAY in .env (default 1.0s).
    """
    if not settings.llm_api_key:
        logger.warning("LLM API key not configured, skipping LLM parsing")
        return []

    # Build deduplicated model chain: primary + fallbacks
    seen: set[str] = set()
    models: list[str] = []
    for m in [settings.llm_model] + settings.llm_fallback_models_list:
        if m not in seen:
            seen.add(m)
            models.append(m)

    rate_limit_delay: float = getattr(settings, "llm_rate_limit_delay", 1.0)
    last_error: Exception | None = None

    async with _get_semaphore():
        # Small delay to spread requests over time
        if rate_limit_delay > 0:
            await asyncio.sleep(rate_limit_delay)

        async with httpx.AsyncClient(timeout=30.0) as client:
            for model in models:
                try:
                    offers = await _call_model(client, model, text)
                    logger.info(f"LLM ({model}) parsed {len(offers)} offer(s)")
                    return offers

                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    if status in _FALLBACK_STATUS_CODES:
                        logger.warning(
                            f"LLM '{model}' returned {status} — trying next fallback"
                        )
                        last_error = e
                        continue
                    # 401 bad key — stop immediately, no point retrying
                    logger.error(
                        f"LLM non-retriable HTTP {status} with '{model}': "
                        f"{e.response.text[:200]}"
                    )
                    return []

                except json.JSONDecodeError as e:
                    logger.error(f"LLM ({model}) invalid JSON: {e}")
                    last_error = e
                    continue

                except Exception as e:
                    logger.error(f"LLM ({model}) unexpected error: {e}")
                    last_error = e
                    continue

    logger.error(f"All {len(models)} LLM model(s) exhausted. Last error: {last_error}")
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
        logger.error(f"Failed to convert LLM result to ParsedOffer: {e}")
        return None
