"""
LLM-based fallback parser for complex/ambiguous price messages.

Supports any OpenAI-compatible API.
Recommended free provider: OpenRouter
  LLM_API_URL=https://openrouter.ai/api/v1
  LLM_API_KEY=sk-or-v1-...
  LLM_MODEL=google/gemma-3-27b-it:free
  LLM_FALLBACK_MODELS=meta-llama/llama-3.3-70b-instruct:free,mistralai/mistral-7b-instruct:free

Alternative: Google Gemini direct
  LLM_API_URL=https://generativelanguage.googleapis.com/v1beta/openai
  LLM_MODEL=gemini-2.0-flash
"""
import json
import logging
from typing import Optional

import httpx

from app.config import settings
from app.parser.regex_parser import ParsedOffer

logger = logging.getLogger(__name__)

# Status codes that should trigger a fallback to next model
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


async def _call_model(client: httpx.AsyncClient, model: str, text: str) -> list[ParsedOffer]:
    """
    Make a single LLM API call for the given model.
    Raises httpx.HTTPStatusError on non-2xx so callers can handle fallback.
    """
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
        logger.warning(f"LLM ({model}) returned unexpected structure: {type(parsed)}")
        return []

    return [o for o in (_dict_to_parsed_offer(i) for i in offers_raw) if o]


async def parse_with_llm(text: str) -> list[ParsedOffer]:
    """
    Parse a message using an LLM with automatic model fallback.

    Tries models in order:
      1. settings.llm_model          (primary)
      2. settings.llm_fallback_models (comma-separated list from .env)

    On 429/404/502/503 automatically moves to next model.
    Returns empty list only when ALL models fail.
    """
    if not settings.llm_api_key:
        logger.warning("LLM API key not configured, skipping LLM parsing")
        return []

    # Build deduplicated model chain
    seen: set[str] = set()
    models: list[str] = []
    for m in [settings.llm_model] + settings.llm_fallback_models_list:
        if m not in seen:
            seen.add(m)
            models.append(m)

    last_error: Exception | None = None

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
                        f"LLM model '{model}' returned {status} — trying next fallback"
                    )
                    last_error = e
                    continue
                # Non-retriable (e.g. 401 bad key) — stop immediately
                logger.error(
                    f"LLM non-retriable HTTP {status} with model '{model}': "
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

    logger.error(
        f"All {len(models)} LLM model(s) exhausted. Last error: {last_error}"
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
        needs_review = data.get("needs_review", False)
        if needs_review:
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
