# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import websockets
import customtkinter as ctk

logger = logging.getLogger(__name__)

def translate_websocket_error(error_message: str) -> str:
    """Переводит технические ошибки websockets на понятный русский язык."""
    error_message_lower = error_message.lower()
    if "no close frame" in error_message_lower:
        return "Соединение было разорвано неожиданно. Возможно, устройство перезагрузилось или пропало питание."
    if "keepalive ping timeout" in error_message_lower:
        return "Устройство не отвечает на проверку связи (пинг). Возможно, оно \"зависло\" или есть проблемы с сетью."
    if "timed out during opening handshake" in error_message_lower:
        return "Не удалось подключиться к устройству. Проверьте IP-адрес и доступность устройства в сети."
    if "getaddrinfo failed" in error_message_lower:
        return "Не удалось распознать IP-адрес устройства. Проверьте правильность адреса в настройках."
    # Можно добавить другие переводы по мере необходимости
    return f"Произошла неизвестная сетевая ошибка: {error_message}"

class BaseController:
    def __init__(self, uri, loop, state_update_callback=None, device_ip=None):
        self.uri = uri
        self.loop = loop
        self.state_update_callback = state_update_callback
        self.device_ip = device_ip
        self.websocket = None
        self.is_connected = False
        self.connection_lost_notified = False # Флаг для отслеживания уведомления о потере связи
        self.target_state = 'disconnected'
        self._main_task_ref = None
        self.reconnect_delay = 5
        self.state = {}
        self.first_disconnection_time = None
        self.disconnection_grace_period = 30
        self.last_connection_error = ""

    def start(self):
        if not self._main_task_ref:
            self.loop.call_soon_threadsafe(self._create_main_task)

    def _create_main_task(self):
        if not self._main_task_ref:
            self._main_task_ref = asyncio.create_task(self._connection_manager())

    def stop_tasks(self):
        if self._main_task_ref:
            self.loop.call_soon_threadsafe(self._main_task_ref.cancel)

    async def _connection_manager(self):
        while True:
            try:
                if self.target_state == 'connected' and not self.is_connected:
                    # Проверяем, истек ли льготный период, ПЕРЕД попыткой переподключения
                    if self.first_disconnection_time is not None and not self.connection_lost_notified:
                        elapsed = self.loop.time() - self.first_disconnection_time
                        if elapsed > self.disconnection_grace_period:
                            logger.error("Превышено допустимое время разрыва (%s с) для %s", self.disconnection_grace_period, self.uri)
                            self.connection_lost_notified = True
                            translated_error = translate_websocket_error(self.last_connection_error)
                            if self.state_update_callback:
                                # Эта функция вызовет показ уведомления
                                self.state_update_callback(self.state, 'error', translated_error)
                    
                    await self._establish_connection()
                    await asyncio.sleep(self.reconnect_delay)
                else:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info(f"Менеджер соединений для {self.uri} остановлен.")
                break
            except Exception as e:
                logger.info(f"Неожиданная ошибка в менеджере соединений {self.uri}: {e}")
                await asyncio.sleep(self.reconnect_delay)

    async def _establish_connection(self):
        if self.state_update_callback:
            self.state_update_callback(self.state, 'connecting')
        try:
            self.websocket = await websockets.connect(self.uri, ping_interval=20, ping_timeout=20, open_timeout=5)
            self.is_connected = True
            logger.info("Установлено соединение с %s", self.uri)

            # Если мы были в состоянии "полностью отключен", уведомляем о восстановлении
            if self.connection_lost_notified:
                if self.state_update_callback:
                    self.state_update_callback(self.state, 'reconnected', "Соединение восстановлено")
            
            # Сбрасываем все флаги и таймеры при успешном подключении
            self.connection_lost_notified = False
            self.first_disconnection_time = None
            self.last_connection_error = ""

            await self._listener()
        except Exception as e:
            logger.info(f"Ошибка подключения к {self.uri}: {e}")
            self.last_connection_error = str(e)
            # Если это первая ошибка в серии, запускаем таймер льготного периода
            if self.first_disconnection_time is None:
                logger.info(f"Потеряно соединение с {self.uri}. Запускаю льготный период...")
                self.first_disconnection_time = self.loop.time()
        finally:
            self.is_connected = False
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
            status_to_report = 'error' if self.target_state == 'connected' else 'disconnected'
            if self.state_update_callback:
                # Вызываем без сообщения об ошибке, чтобы просто обновить UI (цвет в дереве)
                self.state_update_callback(self.state, status_to_report)

    async def _listener(self):
        async for message in self.websocket:
            self._parse_message(message)

    def _parse_message(self, message):
        raise NotImplementedError

    def connect(self):
        self.target_state = 'connected'

    async def disconnect(self):
        self.target_state = 'disconnected'
        if self.websocket:
            await self.websocket.close()
        if self.state_update_callback:
            self.state_update_callback(self.state, 'disconnected')

    async def _send_command(self, payload):
        if not self.is_connected:
            if self.state_update_callback:
                self.state_update_callback(self.state, 'error', 'Устройство офлайн, команда не отправлена.')
            return
        try:
            compact_json = json.dumps(payload, separators=(',', ':'))
            await self.websocket.send(compact_json)
        except Exception as e:
            if self.state_update_callback:
                self.state_update_callback(self.state, 'error', f"Не удалось отправить команду: {e}")


class BaseDeviceFrame(ctk.CTkFrame):
    def __init__(self, master, loop, device_info, status_callback, app=None):
        super().__init__(master, fg_color="transparent")
        self.loop = loop
        self.device_info = device_info
        self.device_name = device_info["name"]
        self.device_ip = device_info["ip"]
        self.status_callback = status_callback
        self.app = app
        self.controller = None
        uri_factory = self.device_info.get("_uri_factory")
        if callable(uri_factory):
            self.uri = uri_factory(self.device_ip)
        else:
            device_type = self.device_info.get("type", "curtain")
            if device_type == "fan":
                self.uri = f"ws://{self.device_ip}:81"
            else:
                self.uri = f"ws://{self.device_ip}/ws"
        self.grid_columnconfigure(0, weight=1)

    def start_controller(self, controller_class):
        if self.controller:
            return
        self.controller = controller_class(self.uri, self.loop, self.on_state_update, device_ip=self.device_ip)
        self.controller.start()
        self.controller.connect()

    def on_state_update(self, state, status, error_message=None):
        self.after(0, self.update_ui, state, status)
        self.status_callback(self.device_name, self.device_info.get("location"), status)

        if status == 'error' and error_message and self.app:
            location = self.device_info.get('location', '').strip()
            title = f"Ошибка: {self.device_name}"
            if location:
                title += f" ({location})"
            self.app.after(0, self.app.show_notification, title, error_message)
        
        elif status == 'reconnected' and error_message and self.app:
            location = self.device_info.get('location', '').strip()
            title = f"Восстановление: {self.device_name}"
            if location:
                title += f" ({location})"
            self.app.after(0, self.app.show_notification, title, error_message, "SUCCESS")

    def update_ui(self, state, status):
        raise NotImplementedError

    def safe_async_call(self, coro):
        if self.controller and self.loop.is_running():
            async def wrapper():
                try:
                    await coro
                except Exception as e:
                    logger.exception("Ошибка safe_async_call для %s: %s", self.device_name, e)
                    if self.app:
                        self.app.show_notification(
                            f"Ошибка: {self.device_name}",
                            f"Не удалось выполнить действие: {e}",
                            level="ERROR"
                        )
            self.loop.call_soon_threadsafe(asyncio.create_task, wrapper())

    def stop_controller_tasks(self):
        if self.controller:
            self.controller.stop_tasks()
