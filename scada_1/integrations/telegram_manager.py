# -*- coding: utf-8 -*-
"""Компоненты интеграции с Telegram."""
import json
import logging
import os
from typing import Callable, Optional

import customtkinter as ctk

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)


class TelegramManager:
    def __init__(self, path: str = "telegram_config.json"):
        self.path = path
        self.config = self.load_or_create()

    def load_or_create(self):
        if not os.path.exists(self.path):
            default_config = {"bot_token": "", "chat_id": ""}
            self.save(default_config)
            return default_config
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as exc:
            logger.error("Ошибка чтения Telegram-конфига '%s': %s", self.path, exc)
            return {"bot_token": "", "chat_id": ""}

    def save(self, data):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            self.config = data
        except IOError as exc:
            logger.error("Ошибка сохранения Telegram-конфига '%s': %s", self.path, exc)

    def get_token(self) -> str:
        return self.config.get("bot_token", "")

    def get_chat_id(self) -> str:
        return self.config.get("chat_id", "")


def send_telegram_message(
    bot_token: str,
    chat_id: str,
    message: str,
    callback: Optional[Callable[[bool, Optional[str]], None]] = None,
) -> None:
    if not requests:
        msg = "Библиотека 'requests' не установлена. Сообщение не отправлено. Установите пакет: pip install requests"
        logger.error(msg)
        if callback and ctk.CTk._get_running_app():
            ctk.CTk._get_running_app().after(0, callback, False, msg)
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        response_data = response.json()
        if response_data.get("ok") is False:
            error_msg = response_data.get("description", "Unknown error")
            logger.error("Telegram API вернул ошибку: %s", error_msg)
            if callback and ctk.CTk._get_running_app():
                ctk.CTk._get_running_app().after(0, callback, False, error_msg)
        else:
            logger.info("Сообщение отправлено в чат %s", chat_id)
            if callback and ctk.CTk._get_running_app():
                ctk.CTk._get_running_app().after(0, callback, True)
    except requests.exceptions.RequestException as exc:
        error_msg = f"Не удалось отправить сообщение: {exc}"
        logger.error("Ошибка отправки сообщения в Telegram: %s", error_msg)
        if callback and ctk.CTk._get_running_app():
            ctk.CTk._get_running_app().after(0, callback, False, error_msg)
