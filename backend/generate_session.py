"""
Утилита для генерации Telegram Session String.

Запустите этот скрипт ОДИН РАЗ на вашем компьютере (не в Docker).
Он попросит номер телефона и код подтверждения из Telegram,
после чего выведет строку сессии, которую нужно вставить в .env.

Использование:
    pip install telethon
    python generate_session.py
"""
import asyncio
import sys

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main():
    print("=" * 60)
    print("  Генератор Telegram Session String")
    print("=" * 60)
    print()
    print("Для работы нужны API ID и API Hash.")
    print("Получить их можно на https://my.telegram.org")
    print()

    api_id = input("Введите API ID: ").strip()
    api_hash = input("Введите API Hash: ").strip()

    if not api_id or not api_hash:
        print("Ошибка: API ID и API Hash обязательны.")
        sys.exit(1)

    try:
        api_id = int(api_id)
    except ValueError:
        print("Ошибка: API ID должен быть числом.")
        sys.exit(1)

    print()
    print("Сейчас Telegram запросит ваш номер телефона,")
    print("затем пришлёт код подтверждения в приложение.")
    print()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        phone = input("Введите номер телефона (в формате +7...): ").strip()
        await client.send_code_request(phone)
        code = input("Введите код из Telegram: ").strip()

        try:
            await client.sign_in(phone, code)
        except Exception:
            # Может потребоваться пароль двухфакторной аутентификации
            password = input("Введите пароль 2FA (если включён): ").strip()
            await client.sign_in(password=password)

    session_string = client.session.save()
    await client.disconnect()

    print()
    print("=" * 60)
    print("  ГОТОВО! Ваша Session String:")
    print("=" * 60)
    print()
    print(session_string)
    print()
    print("=" * 60)
    print()
    print("Скопируйте эту строку и вставьте в файл .env:")
    print(f'TELEGRAM_SESSION_STRING={session_string}')
    print()
    print("ВАЖНО: Эта строка даёт полный доступ к вашему")
    print("Telegram-аккаунту. Не передавайте её третьим лицам!")


if __name__ == "__main__":
    asyncio.run(main())
