# -*- coding: utf-8 -*-
"""Точка входа для SCADA-приложения."""

import asyncio
import threading

import database_manager
from services.config_manager import ConfigManager
from services.logging_setup import configure_logging
from ui.app import App


def run_asyncio_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    configure_logging()
    database_manager.setup_database()

    config_manager = ConfigManager()
    config = config_manager.load_or_create()

    async_loop = asyncio.new_event_loop()
    threading.Thread(target=run_asyncio_loop, args=(async_loop,), daemon=True).start()

    app = App(loop=async_loop, config=config)
    app.mainloop()
    async_loop.call_soon_threadsafe(async_loop.stop)
