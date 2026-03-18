"""
Скрипт для первоначального наполнения системы.

Добавляет поставщиков и источники через API.
Запускайте ПОСЛЕ того как backend уже работает (docker-compose up).

Использование:
    python seed_example.py

Отредактируйте SUPPLIERS и SOURCES под свои реальные каналы.
"""
import requests
import sys

API_BASE = "http://localhost:8000/api"


# ====================================================================
# ПОСТАВЩИКИ — отредактируйте под свои реальные данные
# ====================================================================
SUPPLIERS = [
    {"name": "supplier_a", "display_name": "Поставщик А", "priority": 10},
    {"name": "supplier_b", "display_name": "Поставщик Б", "priority": 5},
    {"name": "supplier_c", "display_name": "Поставщик В", "priority": 3},
    # Добавьте ещё:
    # {"name": "supplier_d", "display_name": "Поставщик Г", "priority": 1},
]


# ====================================================================
# ИСТОЧНИКИ — отредактируйте под свои реальные каналы/группы/ботов
# ====================================================================
# Чтобы узнать telegram_id канала/группы:
#   1. Перешлите сообщение из канала боту @userinfobot
#   2. Или используйте Telegram API: client.get_entity("@channel_name")
#
# Для каналов: telegram_id обычно отрицательное число (например -1001234567890)
# Для ботов: telegram_id — это ID бота (положительное число)

SOURCES = [
    # Пример закрытого канала
    {
        "type": "channel",
        "telegram_id": -1001234567890,  # ← ЗАМЕНИТЕ на реальный ID
        "source_name": "Прайс-канал Поставщика А",
        "supplier_name": "supplier_a",    # Должен совпадать с name из SUPPLIERS
        "poll_interval_minutes": 15,
        "parsing_strategy": "auto",
    },
    # Пример закрытой группы
    {
        "type": "group",
        "telegram_id": -1009876543210,  # ← ЗАМЕНИТЕ на реальный ID
        "source_name": "Группа Поставщика Б",
        "supplier_name": "supplier_b",
        "poll_interval_minutes": 30,
        "parsing_strategy": "auto",
    },
    # Пример бота (сценарий добавляется отдельно)
    {
        "type": "bot",
        "telegram_id": 7123456789,  # ← ЗАМЕНИТЕ на реальный ID бота
        "source_name": "Прайс-бот Поставщика В",
        "supplier_name": "supplier_c",
        "poll_interval_minutes": 60,
        "parsing_strategy": "auto",
    },
]


# ====================================================================
# СЦЕНАРИИ БОТОВ
# ====================================================================
BOT_SCENARIOS = [
    {
        "bot_name": "Прайс-бот Поставщика В",
        "scenario_name": "Получить прайс Apple iPhone",
        "steps_json": [
            {"action": "send_command", "value": "/start", "wait_sec": 3},
            {"action": "click_inline", "value": "Прайс", "wait_sec": 2},
            {"action": "click_inline", "value": "Apple", "wait_sec": 2},
            {"action": "click_inline", "value": "iPhone", "wait_sec": 3},
            {"action": "collect_response", "wait_sec": 0},
        ],
    },
]


def main():
    print("Проверяю доступность API...")
    try:
        r = requests.get(f"{API_BASE}/stats", timeout=5)
        r.raise_for_status()
        print(f"  API доступен: {r.json()}")
    except Exception as e:
        print(f"  ОШИБКА: API недоступен по адресу {API_BASE}")
        print(f"  {e}")
        print()
        print("  Убедитесь что docker-compose up запущен")
        sys.exit(1)

    # Создаём поставщиков
    print()
    print("Создаю поставщиков...")
    supplier_ids = {}
    for s in SUPPLIERS:
        r = requests.post(f"{API_BASE}/suppliers", json=s)
        if r.status_code in (200, 201):
            data = r.json()
            supplier_ids[s["name"]] = data["id"]
            print(f"  ✓ {s['display_name']} (id={data['id']})")
        elif r.status_code == 409 or "already exists" in r.text.lower():
            print(f"  ~ {s['display_name']} — уже существует")
        else:
            print(f"  ✗ {s['display_name']} — ошибка: {r.status_code} {r.text}")

    # Создаём сценарии ботов
    print()
    print("Создаю сценарии ботов...")
    scenario_ids = {}
    for sc in BOT_SCENARIOS:
        r = requests.post(f"{API_BASE}/bot-scenarios", json=sc)
        if r.status_code in (200, 201):
            data = r.json()
            scenario_ids[sc["bot_name"]] = data["id"]
            print(f"  ✓ {sc['scenario_name']} (id={data['id']})")
        else:
            print(f"  ✗ {sc['scenario_name']} — ошибка: {r.status_code} {r.text}")

    # Создаём источники
    print()
    print("Создаю источники...")
    for src in SOURCES:
        payload = {
            "type": src["type"],
            "telegram_id": src["telegram_id"],
            "source_name": src["source_name"],
            "is_active": True,
            "poll_interval_minutes": src["poll_interval_minutes"],
            "parsing_strategy": src["parsing_strategy"],
        }

        # Привязываем поставщика
        sname = src.get("supplier_name")
        if sname and sname in supplier_ids:
            payload["supplier_id"] = supplier_ids[sname]

        # Привязываем сценарий бота
        if src["type"] == "bot" and src["source_name"] in scenario_ids:
            payload["bot_scenario_id"] = scenario_ids[src["source_name"]]

        r = requests.post(f"{API_BASE}/sources", json=payload)
        if r.status_code in (200, 201):
            data = r.json()
            print(f"  ✓ {src['source_name']} [{src['type']}] (id={data['id']})")
        elif r.status_code == 409 or "already exists" in r.text.lower():
            print(f"  ~ {src['source_name']} — уже существует")
        else:
            print(f"  ✗ {src['source_name']} — ошибка: {r.status_code} {r.text}")

    print()
    print("=" * 60)
    print("Готово! Теперь:")
    print("  1. Откройте http://localhost:3000 — веб-интерфейс")
    print("  2. Откройте http://localhost:8000/docs — Swagger API")
    print("  3. Celery автоматически начнёт сбор данных по расписанию")
    print("  4. Или вызовите сбор вручную через API:")
    print("     curl -X POST http://localhost:8000/api/sources/1/collect")
    print()


if __name__ == "__main__":
    main()
