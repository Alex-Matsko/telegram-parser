"""
LLM-based fallback parser for complex/ambiguous price messages.

Ollama .env example:
  LLM_API_URL=http://10.99.99.20:11434/v1
  LLM_API_KEY=ollama
  LLM_MODEL=qwen2.5:7b-instruct-ctx8k
  LLM_FALLBACK_MODELS=
  LLM_RATE_LIMIT_DELAY=0.0
  LLM_CONCURRENCY=4

Groq free tier .env example:
  LLM_API_URL=https://api.groq.com/openai/v1
  LLM_API_KEY=gsk_...
  LLM_MODEL=llama-3.3-70b-versatile
  LLM_FALLBACK_MODELS=llama-3.1-8b-instant
  LLM_RATE_LIMIT_DELAY=2.0
  LLM_CONCURRENCY=1
"""
import asyncio
import json
import logging
from typing import Optional

import httpx

from app.config import settings
from app.parser.regex_parser import ParsedOffer

logger = logging.getLogger(__name__)

_FALLBACK_STATUS_CODES = {400, 429, 404, 503, 502}

# connect быстрый, read большой — LLM может думать долго
_LLM_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)

# Системный промпт ~800 токенов, JSON ответ до 1000 токенов → итого нужно ~2000
_MAX_TOKENS = 2048

SYSTEM_PROMPT = """Ты — модуль нормализации прайсов электроники из Telegram-сообщений.

Твоя задача:
1. Проанализировать входной текст сообщения.
2. Выделить товарные позиции.
3. Для каждой позиции извлечь:
   - category, brand, line, model, memory, color, condition, sim_type, price, currency
4. Привести данные к нормализованному виду.
5. Вернуть результат строго в JSON.
6. Если уверенность < 0.7, установить "needs_review": true.
7. Не додумывать данные, если их нет явно.
8. Если несколько позиций — вернуть массив объектов в поле "items".
9. Если сообщение НЕ является прайсом (обычный чат, вопросы, приветствия) — верни {"items": []}.

== КРИТИЧЕСКИЕ ПРАВИЛА РАЗБОРА ЦИФР ==

1. ПАМЯТЬ vs ЦЕНА:
   - Объём памяти = 32, 64, 128, 256, 512, 1024(=1TB), 2048(=2TB)
   - Эти числа сами по себе — ВСЕГДА memory, НИКОГДА не price
   - RAM/storage формат "X/Y": X = RAM, Y = storage. Пример: "12/512" → memory="512GB"
   - Цена ВСЕГДА >= 1000 руб. или >= 50 USD/EUR
   - Если число < 1000 руб. — это НЕ цена (это модель, RAM, память или количество)

2. ГДЕ ИСКАТЬ ЦЕНУ:
   - Справа от разделителя — тире (—), дефиса (-) или вертикальной черты (|)
   - Если разделителя нет — ПОСЛЕДНЕЕ число в строке (>= 1000)
   - НИКОГДА не принимай число, стоящее ДО разделителя, за цену
   - Количество до цены: "-1 93,500" → цена = 93500 (1 — количество, игнорируй)

3. ФОРМАТЫ ЧИСЕЛ:
   - "62 000", "62.000", "62,000" → 62000
   - "96.500", "96,500" → 96500
   - "13100.00", "13100,00" → 13100
   - "915$" → price=915, currency="USD"

4. ПАМЯТЬ Mac/MacBook (чип+RAM+хранилище):
   - "М4 16GB 256GB" → memory="256GB" (берём ХРАНИЛИЩЕ, игнорируем RAM 16GB)
   - "М4 Pro 24GB 1TB" → memory="1TB"
   - "М4 Max 64GB 1TB" → memory="1TB"

5. SIM-тип:
   - "eSim" → sim_type="esim"
   - "Sim+eSim", "Sim/eSim", "+eSim" → sim_type="dual+esim"
   - "физ", "фыз", "nano", "physical" → sim_type="dual"
   - Нет упоминания → sim_type=null

6. ЦВЕТ: nat/natural→Natural Titanium, bt→Blue Titanium, wt→White Titanium,
   bkt→Black Titanium, dt→Desert Titanium, blk/bk/black→Black, wh/white→White,
   sg→Space Gray, pink→Pink, blue→Blue, green→Green, yellow→Yellow, red→Red,
   purple→Purple, midnight→Midnight, starlight→Starlight, gold→Gold,
   silver→Silver, graphite→Graphite, ultramarine→Ultramarine, teal→Teal,
   rose→Rose, pinkgold/rose gold→Rose Gold. Если не указан — color=null.

7. СОСТОЯНИЕ: new/used/refurbished. По умолчанию new.
   б/у,бу,bu,like new→used; ref,refurb,cpo→refurbished

8. МОДЕЛЬ vs ПАМЯТЬ: "16 256 Black-62700"→model="iPhone 16",memory="256GB" (не model=16256!)

== ОТВЕЧАЙ ТОЛЬКО ВАЛИДНЫМ JSON БЕЗ ПОЯСНЕНИЙ ==
Шаблон: {"items":[{"category":"smartphone","brand":"Apple","line":"iPhone","model":"iPhone 17 Pro","memory":"256GB","color":null,"condition":"new","sim_type":null,"price":96500,"currency":"RUB","confidence":0.9,"needs_review":false}]}
"""

_semaphore_map: dict[int, asyncio.Semaphore] = {}


def _get_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_event_loop()
    loop_id = id(loop)
    if loop_id not in _semaphore_map:
        concurrency = getattr(settings, "llm_concurrency", 2)
        _semaphore_map[loop_id] = asyncio.Semaphore(concurrency)
    return _semaphore_map[loop_id]


async def _call_model(client: httpx.AsyncClient, model: str, text: str) -> list[ParsedOffer]:
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
            "max_tokens": _MAX_TOKENS,
        },
    )
    response.raise_for_status()

    data = response.json()
    content = data["choices"][0]["message"]["content"].strip()

    # Пустой ответ — модель не нашла офферов, это НЕ ошибка
    if not content:
        logger.info(f"LLM ({model}) returned empty response — no offers in message")
        return []

    content = _extract_json(content)

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        raise e

    if isinstance(parsed, dict) and "items" in parsed:
        offers_raw = parsed["items"]
    elif isinstance(parsed, list):
        offers_raw = parsed
    else:
        logger.warning(f"LLM ({model}) unexpected structure: {type(parsed)}")
        return []

    return [o for o in (_dict_to_parsed_offer(i) for i in offers_raw) if o]


async def parse_with_llm(text: str) -> list[ParsedOffer]:
    if not settings.llm_api_key:
        logger.warning("LLM API key not configured, skipping LLM parsing")
        return []

    seen: set[str] = set()
    models: list[str] = []
    for m in [settings.llm_model] + settings.llm_fallback_models_list:
        if m not in seen:
            seen.add(m)
            models.append(m)

    rate_limit_delay: float = getattr(settings, "llm_rate_limit_delay", 0.0)
    last_error: Exception | None = None

    async with _get_semaphore():
        if rate_limit_delay > 0:
            await asyncio.sleep(rate_limit_delay)

        async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
            for model in models:
                for attempt in range(3):
                    try:
                        offers = await _call_model(client, model, text)
                        logger.info(f"LLM ({model}) parsed {len(offers)} offer(s)")
                        return offers

                    except httpx.HTTPStatusError as e:
                        status = e.response.status_code
                        if status in _FALLBACK_STATUS_CODES:
                            logger.warning(f"LLM '{model}' returned {status} — trying next fallback")
                            last_error = e
                            break
                        logger.error(f"LLM non-retriable HTTP {status} with '{model}': {e.response.text[:300]}")
                        return []

                    except json.JSONDecodeError as e:
                        if attempt < 2:
                            logger.warning(f"LLM ({model}) invalid JSON, retry {attempt + 1}/2")
                            await asyncio.sleep(1.0)
                            continue
                        logger.error(f"LLM ({model}) invalid JSON after retries: {e}")
                        last_error = e
                        break

                    except ValueError as e:
                        logger.error(f"LLM ({model}) parse error: {type(e).__name__}: {e}")
                        last_error = e
                        break

                    except httpx.ReadTimeout:
                        logger.error(f"LLM ({model}) read timeout — trying next model")
                        last_error = Exception("ReadTimeout")
                        break

                    except Exception as e:
                        logger.error(f"LLM ({model}) unexpected error: {type(e).__name__}: {e!r}")
                        last_error = e
                        break

    logger.error(f"All {len(models)} LLM model(s) exhausted. Last error: {last_error}")
    return []


async def parse_with_llm_batch(texts: list[str]) -> list[list[ParsedOffer]]:
    """Оставлено для обратной совместимости. Используй parse_with_llm напрямую."""
    results = []
    for text in texts:
        try:
            offers = await parse_with_llm(text)
            results.append(offers)
        except Exception as e:
            logger.error(f"LLM batch item failed: {e}")
            results.append([])
    return results


def _extract_json(content: str) -> str:
    if "```json" in content:
        try:
            start = content.index("```json") + 7
            end = content.index("```", start)
            return content[start:end].strip()
        except ValueError:
            pass
    if "```" in content:
        try:
            start = content.index("```") + 3
            end = content.index("```", start)
            return content[start:end].strip()
        except ValueError:
            pass
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
            brand=data.get("brand", "Unknown"),
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
