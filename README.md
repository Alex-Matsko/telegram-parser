# TG Price Monitor — Система агрегации прайсов из Telegram

Автоматический сбор, нормализация и сравнение цен на технику из закрытых Telegram-каналов, групп и ботов.

## Возможности

- **Сбор данных** из закрытых каналов, групп и интерактивных ботов через Telegram-аккаунт
- **Парсинг** неструктурированных сообщений (regex + словари синонимов + LLM)
- **Нормализация** к единому SKU (iPhone 15 PM 256 Nat → `smartphone/apple/iphone_15_pro_max/256gb/natural_titanium/new`)
- **Сводный прайс** с минимальной ценой, лучшим поставщиком, альтернативами
- **История цен** за 3 дня по каждому товару и поставщику
- **Очередь ошибок** для ручного разбора неразобранных сообщений
- **Сценарии ботов** — настраиваемые последовательности кнопок для получения прайсов

## Архитектура

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Telegram    │────▶│  Collector   │────▶│  Raw Layer   │
│  Sources     │     │  (Telethon)  │     │  (PostgreSQL)│
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                    ┌──────────────┐              │
                    │  Parser      │◀─────────────┘
                    │  regex+LLM   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐     ┌─────────────┐
                    │ Normalizer   │────▶│  Catalog +   │
                    │ SKU Matching │     │  Offers +    │
                    └──────────────┘     │  History     │
                                         └──────┬──────┘
                    ┌──────────────┐              │
                    │  FastAPI     │◀─────────────┘
                    │  Backend     │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  React       │
                    │  Frontend    │
                    └──────────────┘
```

## Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic |
| Telegram | Telethon |
| Очереди | Celery + Redis |
| БД | PostgreSQL 15 |
| Парсинг | Regex + LLM (OpenAI-совместимый API) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Графики | Recharts |
| Таблицы | TanStack Table |
| Контейнеризация | Docker Compose |

## Быстрый старт

### 1. Клонируйте и настройте

```bash
cp .env.example .env
# Отредактируйте .env — заполните TELEGRAM_API_ID, TELEGRAM_API_HASH, LLM_API_KEY
```

### 2. Получите Telegram API credentials

1. Перейдите на https://my.telegram.org
2. Войдите с вашим номером телефона
3. Создайте приложение → получите `api_id` и `api_hash`
4. Впишите их в `.env`

### 3. Запустите всю систему

```bash
docker-compose up --build
```

Сервисы:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs

### 4. Демо-режим (без Telegram)

Если хотите посмотреть интерфейс с моковыми данными без настройки Telegram:

```bash
VITE_USE_MOCKS=true docker-compose up frontend
```

Или локально:
```bash
cd frontend
echo "VITE_USE_MOCKS=true" > .env
npm install
npm run dev
```

## Структура проекта

```
telegram-price-aggregator/
├── docker-compose.yml          # Оркестрация всех сервисов
├── .env.example                # Шаблон переменных окружения
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini             # Конфигурация миграций
│   ├── alembic/                # Миграции БД
│   ├── app/
│   │   ├── main.py             # FastAPI приложение
│   │   ├── config.py           # Настройки (pydantic-settings)
│   │   ├── database.py         # SQLAlchemy async engine
│   │   ├── models/             # 7 моделей БД
│   │   ├── schemas/            # Pydantic-схемы API
│   │   ├── api/                # REST-эндпоинты
│   │   ├── collector/          # Telegram-коллектор
│   │   ├── parser/             # Парсер + нормализатор
│   │   ├── tasks/              # Celery-задачи
│   │   └── services/           # Бизнес-логика
│   └── tests/
├── frontend/
│   ├── Dockerfile
│   ├── src/
│   │   ├── api/                # API-клиент + моковые данные
│   │   ├── components/         # React-компоненты
│   │   ├── pages/              # Страницы (прайс, история, источники, ошибки)
│   │   └── types/              # TypeScript типы
│   └── public/
└── README.md
```

## API-эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/price-list` | Сводный прайс с фильтрами |
| GET | `/api/price-list/{id}` | Детали товара со всеми предложениями |
| GET | `/api/history/{id}` | История цен по товару |
| GET | `/api/history/{id}/chart` | Данные для графика |
| GET | `/api/sources` | Список источников |
| POST | `/api/sources` | Добавить источник |
| PUT | `/api/sources/{id}` | Редактировать источник |
| GET | `/api/suppliers` | Список поставщиков |
| POST | `/api/suppliers` | Добавить поставщика |
| GET | `/api/unresolved` | Неразобранные сообщения |
| POST | `/api/unresolved/{id}/resolve` | Ручной разбор |
| GET | `/api/bot-scenarios` | Сценарии ботов |
| POST | `/api/bot-scenarios` | Создать сценарий |
| GET | `/api/stats` | Статистика дашборда |

## Парсер сообщений

Система использует трёхуровневый парсинг:

1. **Regex + словари** — быстрый разбор типовых форматов
2. **LLM** — fallback для сложных/нестандартных сообщений
3. **Ручной разбор** — очередь для неопознанных записей

### Примеры распознавания

| Вход | Результат |
|------|-----------|
| `15 Pro Max 256 nat - 915$` | iPhone 15 Pro Max, 256GB, Natural Titanium, $915 |
| `iPhone 15 PM 256 Natural 91 500` | iPhone 15 Pro Max, 256GB, Natural Titanium, ₽91500 |
| `16/256 black esim 101000` | iPhone 16, 256GB, Black, eSIM, ₽101000 |
| `AirPods Pro 2 USB-C 14500` | AirPods Pro 2 USB-C, ₽14500 |

## Настройка сценариев ботов

Для каждого бота создаётся JSON-сценарий:

```json
[
  {"action": "send_command", "value": "/start", "wait_sec": 2},
  {"action": "click_inline", "value": "Прайс", "wait_sec": 2},
  {"action": "click_inline", "value": "Apple", "wait_sec": 2},
  {"action": "click_inline", "value": "iPhone", "wait_sec": 3},
  {"action": "collect_response", "wait_sec": 0}
]
```

Поддерживаемые действия:
- `send_command` — отправить команду боту
- `send_text` — отправить текст
- `click_inline` — нажать inline-кнопку
- `click_reply` — нажать reply-кнопку
- `collect_response` — собрать ответ для парсинга
- `wait` — подождать N секунд

## Celery-задачи (автоматические)

| Задача | Интервал | Описание |
|--------|----------|----------|
| `collect_from_sources` | 15 мин | Чтение новых сообщений из каналов/групп |
| `execute_bot_scenarios` | 30 мин | Получение прайсов от ботов |
| `parse_raw_messages` | 5 мин | Парсинг необработанных сообщений |
| `refresh_price_list` | 10 мин | Пересчёт сводной витрины |

## Лицензия

Для внутреннего использования.
