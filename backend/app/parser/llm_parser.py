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
   - В строке вида "Xgb Ygb" — меньшее число это RAM, большее — storage

5. SIM-тип:
   - "eSim" → sim_type="esim"
   - "Sim+eSim", "Sim/eSim", "+eSim" → sim_type="dual+esim"
   - "физ", "фыз", "nano", "physical" → sim_type="dual"
   - Нет упоминания → sim_type=null

6. ЦВЕТ (полный список сокращений):
   - nat, natural → "Natural Titanium"
   - bt → "Blue Titanium", wt → "White Titanium", bkt → "Black Titanium", dt → "Desert Titanium"
   - blk, bk, black → "Black", wh, white → "White", sg → "Space Gray"
   - pink → "Pink", blue → "Blue", green → "Green", yellow → "Yellow"
   - red → "Red", purple → "Purple", midnight → "Midnight", starlight → "Starlight"
   - gold → "Gold", silver → "Silver", graphite → "Graphite"
   - ultramarine → "Ultramarine", teal → "Teal", rose → "Rose"
   - pinkgold, rose gold → "Rose Gold"
   - Если цвет не указан явно — color=null

7. СОСТОЯНИЕ: new / used / refurbished. По умолчанию new.
   - б/у, бу, bu, like new → "used"
   - ref, refurb, cpo → "refurbished"

8. МОДЕЛЬ vs ПАМЯТЬ — примеры частых ошибок:
   - "16 256 Black - 62700" → model="iPhone 16", memory="256GB", price=62700 (НЕ model=16256)
   - "17 Pro 256" → model="iPhone 17 Pro", memory="256GB" (256 — это память, не модель)
   - "S26 Ultra 512" → model="Galaxy S26 Ultra", memory="512GB" (26 — номер модели)
   - "13 128" → model="iPhone 13", memory="128GB"

== РАЗРЕШЕННЫЕ ЗНАЧЕНИЯ ==

line: iPhone / AirPods / Apple Watch / MacBook / iPad / Mac / Apple TV /
      Galaxy / Samsung Accessory / Huawei Mate / Huawei Pura / Huawei Nova /
      Honor Magic / Honor / OnePlus / Nintendo Switch / Meta Quest /
      GoPro / Canon / Insta360 / Dyson / Dell

category: smartphone / headphones / watch / laptop / tablet / desktop /
          camera / console / vr / appliance / tv / accessory

condition: new / used / refurbished
currency: RUB / USD / EUR
memory: 32GB / 64GB / 128GB / 256GB / 512GB / 1TB / 2TB
sim_type: single / dual / esim / dual+esim / null

== ПРИМЕРЫ (input → ожидаемый output) ==

Цена справа от тире:
  "17 Pro 256 Blue — 96500"
  → {model:"iPhone 17 Pro", memory:"256GB", color:"Blue", price:96500, currency:"RUB"}

Цена с точкой как разделителем тысяч:
  "17 Pro 256 Blue — 96.500"
  → {model:"iPhone 17 Pro", memory:"256GB", color:"Blue", price:96500}

Цена с пробелом:
  "15 Pro Max 256 nat — 91 500"
  → {model:"iPhone 15 Pro Max", memory:"256GB", color:"Natural Titanium", price:91500}

RAM/storage (не путать с ценой):
  "Galaxy S25 Ultra 12/512 Phantom Black — 94000"
  → {model:"Galaxy S25 Ultra", memory:"512GB", color:"Phantom Black", price:94000}

RAM Mac (брать хранилище, не RAM):
  "MacBook Air 13 M4 16GB 256GB — 84500"
  → {model:"MacBook Air 13", memory:"256GB", price:84500}

Mac Pro RAM + большое хранилище:
  "MacBook Pro 16 M4 Pro 24GB 1TB — 189000"
  → {model:"MacBook Pro 16", memory:"1TB", price:189000}

Формат с пайпом:
  "16 | 256 | Black | 62700"
  → {model:"iPhone 16", memory:"256GB", color:"Black", price:62700}

Цена в конце без тире:
  "17 256 Black Sim+eSim 61700"
  → {model:"iPhone 17", memory:"256GB", color:"Black", sim_type:"dual+esim", price:61700}

Копейки:
  "13100.00 ₽"
  → {price:13100, currency:"RUB"}

Количество перед ценой:
  "17 pro 256 blue eSIM -1 93,500"
  → {model:"iPhone 17 Pro", memory:"256GB", color:"Blue", sim_type:"esim", price:93500}

Artifact backtick:
  "16 256 black 62700`"
  → {model:"iPhone 16", memory:"256GB", color:"Black", price:62700}

eSim:
  "**17 Pro Max 256 Blue (eSim) — 107200 **"
  → {model:"iPhone 17 Pro Max", memory:"256GB", color:"Blue", sim_type:"esim", price:107200}

AirPods:
  "AirPods Pro 2 USB-C — 14500"
  → {line:"AirPods", model:"AirPods Pro 2 USB-C", category:"headphones", price:14500}

Apple Watch:
  "Apple Watch Ultra 2 — 58000"
  → {line:"Apple Watch", model:"Apple Watch Ultra 2", category:"watch", price:58000}

USD:
  "15 Pro Max 256 nat — 915$"
  → {model:"iPhone 15 Pro Max", memory:"256GB", color:"Natural Titanium", price:915, currency:"USD"}

Samsung c RAM/storage:
  "S25 Ultra 12/512 Phantom Black — 94000"
  → {line:"Galaxy", model:"Galaxy S25 Ultra", memory:"512GB", color:"Phantom Black", price:94000}

Nintendo:
  "Nintendo Switch OLED — 28000"
  → {line:"Nintendo Switch", model:"Nintendo Switch OLED", category:"console", price:28000}

GoPro:
  "GoPro Hero 13 Black — 42000"
  → {line:"GoPro", model:"GoPro Hero 13 Black", category:"camera", price:42000}

Б/У:
  "iPhone 13 128GB Pink б/у — 32000"
  → {model:"iPhone 13", memory:"128GB", color:"Pink", condition:"used", price:32000}

Несколько позиций:
  "16 Pro 256 Nat — 91000\n16 Pro 512 Nat — 101000"
  → {items:[{model:"iPhone 16 Pro", memory:"256GB", color:"Natural Titanium", price:91000},
             {model:"iPhone 16 Pro", memory:"512GB", color:"Natural Titanium", price:101000}]}

ЧАСТЫЕ ОШИБКИ — никогда не делай так:
  НЕПРАВИЛЬНО: "16 256 Black - 62700" → model="16256"  (никогда не склеивай номер модели с памятью!)
  ПРАВИЛЬНО:   "16 256 Black - 62700" → model="iPhone 16", memory="256GB", price=62700

  НЕПРАВИЛЬНО: "17 Pro 256 Blue - 96500" → price=256  (256 — это память, не цена!)
  ПРАВИЛЬНО:   "17 Pro 256 Blue - 96500" → memory="256GB", price=96500

  НЕПРАВИЛЬНО: "S26 12/512 Black - 94000" → memory="12GB"  (берём storage, не RAM!)
  ПРАВИЛЬНО:   "S26 12/512 Black - 94000" → memory="512GB", price=94000

== ОТВЕЧАЙ ТОЛЬКО ВАЛИДНЫМ JSON БЕЗ ПОЯСНЕНИЙ И ТЕКСТА СНАРУЖИ ==
Шаблон: {"items":[{"category":"smartphone","brand":"Apple","line":"iPhone","model":"iPhone 17 Pro","memory":"256GB","color":null,"condition":"new","sim_type":null,"price":96500,"currency":"RUB","confidence":0.9,"needs_review":false}]}
"""

# Семафор per event loop — безопасно для Celery prefork.
# Каждый воркер-процесс имеет свой loop и свой семафор.
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
            "max_tokens": 4096,
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

        async with httpx.AsyncClient(timeout=120.0) as client:
            for model in models:
                try:
                    offers = await _call_model(client, model, text)
                    logger.info(f"LLM ({model}) parsed {len(offers)} offer(s)")
                    return offers

                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    if status in _FALLBACK_STATUS_CODES:
                        logger.warning(f"LLM '{model}' returned {status} — trying next fallback")
                        last_error = e
                        continue
                    logger.error(
                        f"LLM non-retriable HTTP {status} with '{model}': "
                        f"{e.response.text[:300]}"
                    )
                    return []

                except json.JSONDecodeError as e:
                    logger.error(f"LLM ({model}) invalid JSON: {e}")
                    last_error = e
                    continue

                except Exception as e:
                    logger.error(f"LLM ({model}) unexpected error: {type(e).__name__}: {e!r}")
                    last_error = e
                    continue

    logger.error(f"All {len(models)} LLM model(s) exhausted. Last error: {last_error}")
    return []


async def parse_with_llm_batch(texts: list[str]) -> list[list[ParsedOffer]]:
    """
    Параллельная обработка нескольких сообщений через LLM.
    Concurrency ограничен семафором (LLM_CONCURRENCY).
    Возвращает список результатов в том же порядке что входные тексты.
    """
    tasks = [parse_with_llm(text) for text in texts]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    output = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"LLM batch item {i} failed: {result}")
            output.append([])
        else:
            output.append(result)
    return output


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
