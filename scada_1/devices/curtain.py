# -*- coding: utf-8 -*-
import json
import logging
import customtkinter as ctk
from .base_device import BaseController, BaseDeviceFrame

logger = logging.getLogger(__name__)

class CurtainController(BaseController):
    def _parse_message(self, message):
        try:
            self.state = json.loads(message)
            if self.state_update_callback:
                self.state_update_callback(self.state, 'connected')
        except json.JSONDecodeError:
            logger.warning(f"Ошибка декодирования JSON шторы: {message}")

    async def _send_curtain_command(self, command, value=None):
        payload = {"command": command}
        if value is not None:
            payload["value"] = value
        await self._send_command(payload)

    async def open(self):
        await self._send_curtain_command("open")

    async def close(self):
        await self._send_curtain_command("close")

    async def stop(self):
        await self._send_curtain_command("stop")

    async def goto(self, position: int):
        await self._send_curtain_command("goto", position)

    async def calibrate_full(self):
        await self._send_curtain_command("calibrate_full")

    async def reset_error(self):
        await self._send_curtain_command("reset_error")


class CurtainControlFrame(BaseDeviceFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Отслеживаем последнее известное состояние, чтобы не обновлять UI без надобности
        self._last_known_state = {}
        # Отслеживаем последнее известное состояние ошибки, чтобы не спамить диалогами
        self._last_known_error_state = {'vfd_active': True, 'vfd_error': 0}
        title_label = ctk.CTkLabel(self, text=self.device_name, font=ctk.CTkFont(size=20, weight="bold"))
        title_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        self.status_frame = ctk.CTkFrame(self)
        self.status_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        self.controls_frame = ctk.CTkFrame(self)
        self.controls_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=18, weight="bold"))
        self.status_label.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="ew")
        self._create_status_widgets()
        self._create_control_widgets()
        self.update_ui({}, "disconnected")

    def _create_status_widgets(self):
        self.progress_bar = ctk.CTkProgressBar(self.status_frame, height=20)
        self.progress_bar.pack(fill="x", padx=10, pady=10)
        info_panel = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        info_panel.pack(fill="x", padx=10)
        info_panel.grid_columnconfigure((0, 1), weight=1)
        self.position_label = ctk.CTkLabel(info_panel, text="Позиция: -/-")
        self.position_label.grid(row=0, column=0, sticky="w")
        self.current_label = ctk.CTkLabel(info_panel, text="Ток: - A")
        self.current_label.grid(row=1, column=0, sticky="w")
        self.calibrated_label = ctk.CTkLabel(info_panel, text="Калибровка: неизвестно")
        self.calibrated_label.grid(row=2, column=0, sticky="w")
        vfd_error_frame = ctk.CTkFrame(info_panel, fg_color="transparent")
        vfd_error_frame.grid(row=0, column=1, rowspan=3, sticky="e")
        ctk.CTkLabel(vfd_error_frame, text="Ошибка ПЧ:").pack(anchor="e")
        self.vfd_error_label = ctk.CTkLabel(vfd_error_frame, text="--", font=ctk.CTkFont(weight="bold"))
        self.vfd_error_label.pack(anchor="e")
        ctk.CTkLabel(vfd_error_frame, text="Связь с ПЧ:").pack(anchor="e")
        self.vfd_comm_label = ctk.CTkLabel(vfd_error_frame, text="--", font=ctk.CTkFont(weight="bold"))
        self.vfd_comm_label.pack(anchor="e")

    def _create_control_widgets(self):
        open_close_frame = ctk.CTkFrame(self.controls_frame)
        open_close_frame.pack(fill="x", padx=10, pady=5)
        open_close_frame.grid_columnconfigure((0, 1), weight=1)
        self.open_button = ctk.CTkButton(open_close_frame, text="Открыть", command=lambda: self.safe_async_call(self.controller.open()))
        self.open_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.close_button = ctk.CTkButton(open_close_frame, text="Закрыть", command=lambda: self.safe_async_call(self.controller.close()))
        self.close_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.stop_button = ctk.CTkButton(self.controls_frame, text="СТОП", fg_color="#D32F2F", hover_color="#B71C1C", command=lambda: self.safe_async_call(self.controller.stop()))
        self.stop_button.pack(fill="x", padx=10, pady=5)
        slider_frame = ctk.CTkFrame(self.controls_frame)
        slider_frame.pack(fill="x", padx=10, pady=5)
        self.slider_label = ctk.CTkLabel(slider_frame, text="Позиция: 50%")
        self.slider_label.pack()
        self.slider = ctk.CTkSlider(slider_frame, from_=0, to=100, command=lambda v: self.slider_label.configure(text=f"Позиция: {int(v)}%"))
        self.slider.set(50)
        self.slider.pack(fill="x", padx=10)
        self.goto_button = ctk.CTkButton(slider_frame, text="Перейти", command=lambda: self.safe_async_call(self.controller.goto(int(self.slider.get()))))
        self.goto_button.pack(pady=5)

    def _get_all_controls(self):
        """Возвращает список всех интерактивных виджетов."""
        return [w for w in [self.open_button, self.close_button, self.stop_button, self.slider, self.goto_button] if w and w.winfo_exists()]

    def _enable_all_controls(self, enable):
        """Включает или отключает все элементы управления."""
        for widget in self._get_all_controls():
            widget.configure(state="normal" if enable else "disabled")

    def _disconnect_ui(self):
        """Сбрасывает UI в состояние 'отключено'."""
        self._enable_all_controls(False)
        self.status_label.configure(text='ОТКЛЮЧЕНО', text_color="gray")
        self.progress_bar.set(0)
        self.position_label.configure(text="Позиция: -/-", text_color="gray")
        self.current_label.configure(text="Ток: - A", text_color="gray")
        self.calibrated_label.configure(text="Калибровка: неизвестно", text_color="gray")
        self.vfd_error_label.configure(text="--", text_color="gray")
        self.vfd_comm_label.configure(text="--", text_color="gray")

    def update_ui(self, state, status):
        # 1. Обработка отключения
        if status != 'connected' or not state:
            if self._last_known_state.get('status') != 'disconnected':
                self._disconnect_ui()
                self._last_known_state = {'status': 'disconnected'}
            return

        # 2. Принудительное обновление при переподключении
        if self._last_known_state.get('status') == 'disconnected':
            self._enable_all_controls(True)
            self._last_known_state = {}

        # 3. Выход, если данные не изменились
        if state == self._last_known_state:
            return

        old_state = self._last_known_state

        # 4. Обновление UI по частям
        # --- Проверка ошибок ---
        new_vfd_error = state.get("vfd_error", 0)
        new_vfd_active = state.get("vfd_active", False)
        if self.app:
            # Ошибка ЧП (например, перегрузка)
            if new_vfd_error != 0 and new_vfd_error != self._last_known_error_state['vfd_error']:
                self.app.show_notification(f"Ошибка: {self.device_name} ({self.device_info.get('location')})", f"Частотный преобразователь сообщил об ошибке. Код: {new_vfd_error}")
            # Потеря связи с ЧП
            if not new_vfd_active and self._last_known_error_state['vfd_active']:
                self.app.show_notification(f"Ошибка: {self.device_name} ({self.device_info.get('location')})", "Потеряна связь с частотным преобразователем (ПЧ).")
        self._last_known_error_state = {'vfd_active': new_vfd_active, 'vfd_error': new_vfd_error}
        # --- Конец блока ---

        if state.get("state") != old_state.get("state"):
            status_text = state.get("state", "НЕИЗВЕСТНО")
            color_map = {"OPENING": "#4CAF50", "CLOSING": "#FF9800", "STOPPED": "gray", "ERROR_STALLED": "#F44336"}
            self.status_label.configure(text=status_text, text_color=color_map.get(status_text, "white"))

        if state.get("position_percent") != old_state.get("position_percent"):
            pos_percent = state.get("position_percent", 0) / 100.0
            self.progress_bar.set(pos_percent)
            pos_ms = state.get("position_ms", 0)
            travel_time_s = state.get("travel_time", 0)
            self.position_label.configure(text=f"Позиция: {pos_ms / 1000.0:.1f}с / {travel_time_s:.1f}с ({state.get('position_percent', 0)}%)", text_color="white")

        if state.get('current') != old_state.get('current') or state.get('current_avg') != old_state.get('current_avg'):
            self.current_label.configure(text=f"Ток: {state.get('current', 0):.2f}А (сред: {state.get('current_avg', 0):.2f}А)", text_color="white")
        
        if state.get("is_calibrated") != old_state.get("is_calibrated"):
            is_calibrated = state.get("is_calibrated", False)
            self.calibrated_label.configure(text=f"Калибровка: {'Да' if is_calibrated else 'Нет'}", text_color="green" if is_calibrated else "red")
        
        if state.get("vfd_error") != old_state.get("vfd_error"):
            vfd_error = state.get("vfd_error", 0)
            self.vfd_error_label.configure(text=str(vfd_error), text_color="red" if vfd_error != 0 else "white")

        if state.get("vfd_active") != old_state.get("vfd_active"):
            vfd_active = state.get("vfd_active", False)
            self.vfd_comm_label.configure(text="Активно" if vfd_active else "Нет связи", text_color="green" if vfd_active else "red")
        
        self._last_known_state = state.copy()
