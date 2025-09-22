# -*- coding: utf-8 -*-
import json
import logging
import customtkinter as ctk
from .base_device import BaseController, BaseDeviceFrame

logger = logging.getLogger(__name__)

class FanController(BaseController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = {"system": {}, "fan1": {}, "fan2": {}}

    def _parse_message(self, message):
        try:
            data = json.loads(message)
            updated = False
            param = data.get("param")
            value = data.get("value")
            if param == "config" and "num_fans" in data:
                self.state["system"]["num_fans"] = data["num_fans"]
                updated = True
            elif "fan" in data and param is not None and value is not None:
                fan_id = data["fan"]
                if fan_id == 0:
                    if param == 'auto':
                        self.state["system"][param] = bool(int(value))
                    else:
                        self.state["system"][param] = value
                elif fan_id in [1, 2]:
                    self.state[f"fan{fan_id}"][param] = value
                updated = True
            elif param is not None and value is not None:
                if param == 'auto':
                    self.state["system"][param] = bool(int(value))
                else:
                    self.state["system"][param] = value
                updated = True
            elif "sensor_check" in data:
                logger.warning(f"Получен результат проверки датчика: {data}")
                self.state["system"]["last_sensor_check"] = data["sensor_check"]
                updated = True
            if updated and self.state_update_callback:
                self.state_update_callback(self.state, 'connected')
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Ошибка декодирования/парсинга JSON вентилятора: {message}, {e}")

    async def _send_fan_command(self, cmd, fan=0, value=None):
        payload = {"cmd": cmd, "fan": fan}
        if value is not None:
            payload["value"] = value
        await self._send_command(payload)

    async def set_auto_mode(self, enabled: bool):
        await self._send_fan_command("auto", value=1 if enabled else 0)

    async def start_fan(self, fan_id: int):
        await self._send_fan_command("start", fan=fan_id)

    async def stop_fan(self, fan_id: int):
        await self._send_fan_command("stop", fan=fan_id)

    async def set_speed(self, fan_id: int, speed: int):
        await self._send_fan_command("speed", fan=fan_id, value=speed)

    async def reset_error(self, fan_id: int):
        await self._send_fan_command("reset_error", fan=fan_id)


class FanControlFrame(BaseDeviceFrame):
    STATUS_MAP = {
        1: "Работает",
        3: "Остановлен",
    }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Отслеживаем последнее известное состояние ошибки, чтобы не спамить диалогами
        self._last_known_error_state = {
            'temp_error': 0,
            'fan1_error': 0,
            'fan2_error': 0
        }
        title_label = ctk.CTkLabel(self, text=self.device_name, font=ctk.CTkFont(size=20, weight="bold"))
        title_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        self.grid_columnconfigure(0, weight=1)
        self._create_system_widgets()
        self._create_fan_widgets(1)
        self._create_fan_widgets(2)
        self.update_ui({}, "disconnected")

    def _create_system_widgets(self):
        system_frame = ctk.CTkFrame(self)
        system_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        system_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        ctk.CTkLabel(system_frame, text="Температура:").grid(row=0, column=0, pady=5)
        self.temp_label = ctk.CTkLabel(system_frame, text="- °C", font=ctk.CTkFont(weight="bold"))
        self.temp_label.grid(row=1, column=0)
        self.auto_mode_switch = ctk.CTkSwitch(system_frame, text="Авто-режим", command=lambda: self.safe_async_call(self.controller.set_auto_mode(bool(self.auto_mode_switch.get()))))
        self.auto_mode_switch.grid(row=0, column=1, rowspan=2)
        ctk.CTkLabel(system_frame, text="Опрыскивание:").grid(row=0, column=2, pady=5)
        self.spraying_label = ctk.CTkLabel(system_frame, text="Нет", font=ctk.CTkFont(weight="bold"))
        self.spraying_label.grid(row=1, column=2)
        ctk.CTkLabel(system_frame, text="Датчик:").grid(row=0, column=3, pady=5)
        self.sensor_label = ctk.CTkLabel(system_frame, text="Нет данных", font=ctk.CTkFont(weight="bold"))
        self.sensor_label.grid(row=1, column=3)

    def _create_fan_widgets(self, fan_id):
        fan_frame = ctk.CTkFrame(self, border_width=2)
        fan_frame.grid(row=fan_id + 1, column=0, padx=10, pady=5, sticky="ew")
        fan_frame.grid_columnconfigure(1, weight=1)
        setattr(self, f"fan_{fan_id}_frame", fan_frame)
        status_frame = ctk.CTkFrame(fan_frame, fg_color="transparent")
        status_frame.grid(row=0, column=0, rowspan=3, padx=10, pady=10)
        ctk.CTkLabel(status_frame, text=f"Вентилятор #{fan_id}", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 10))
        label_status = ctk.CTkLabel(status_frame, text="Статус: --")
        label_status.pack(anchor="w")
        error_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        error_frame.pack(anchor="w", fill="x")
        ctk.CTkLabel(error_frame, text="Ошибка: ").pack(side="left")
        label_error_value = ctk.CTkLabel(error_frame, text="Нет")
        label_error_value.pack(side="left")
        label_current = ctk.CTkLabel(status_frame, text="Ток: -- A")
        label_current.pack(anchor="w")
        label_freq = ctk.CTkLabel(status_frame, text="Частота: -- Hz")
        label_freq.pack(anchor="w")
        setattr(self, f"fan_{fan_id}_status_label", label_status)
        setattr(self, f"fan_{fan_id}_error_label", label_error_value)
        setattr(self, f"fan_{fan_id}_current_label", label_current)
        setattr(self, f"fan_{fan_id}_freq_label", label_freq)
        control_frame = ctk.CTkFrame(fan_frame, fg_color="transparent")
        control_frame.grid(row=0, column=1, rowspan=3, pady=10)
        btn_start = ctk.CTkButton(control_frame, text="Старт", command=lambda: self.safe_async_call(self.controller.start_fan(fan_id)))
        btn_start.pack(fill="x", padx=5, pady=2)
        btn_stop = ctk.CTkButton(control_frame, text="Стоп", command=lambda: self.safe_async_call(self.controller.stop_fan(fan_id)), fg_color="#D32F2F", hover_color="#B71C1C")
        btn_stop.pack(fill="x", padx=5, pady=2)
        btn_reset = ctk.CTkButton(control_frame, text="Сброс ошибки", command=lambda: self.safe_async_call(self.controller.reset_error(fan_id)), fg_color="gray")
        btn_reset.pack(fill="x", padx=5, pady=2)
        setattr(self, f"fan_{fan_id}_control_buttons", [btn_start, btn_stop, btn_reset])
        speed_frame = ctk.CTkFrame(fan_frame, fg_color="transparent")
        speed_frame.grid(row=0, column=2, rowspan=3, padx=10, pady=10)
        slider_label = ctk.CTkLabel(speed_frame, text="Скорость: 50%")
        slider_label.pack()
        slider = ctk.CTkSlider(speed_frame, from_=0, to=100, command=lambda v, lbl=slider_label: lbl.configure(text=f"Скорость: {int(v)}%"))
        slider.set(50)
        slider.pack(pady=5)
        btn_set_speed = ctk.CTkButton(speed_frame, text="Установить", command=lambda s=slider: self.safe_async_call(self.controller.set_speed(fan_id, int(s.get()))))
        btn_set_speed.pack()
        setattr(self, f"fan_{fan_id}_speed_slider", slider)
        setattr(self, f"fan_{fan_id}_speed_button", btn_set_speed)

    def update_ui(self, state, status):
        all_widgets = [self.auto_mode_switch]
        for i in [1, 2]:
            all_widgets.extend(getattr(self, f"fan_{i}_control_buttons", []))
            all_widgets.append(getattr(self, f"fan_{i}_speed_slider", None))
            all_widgets.append(getattr(self, f"fan_{i}_speed_button", None))
        if status != 'connected' or not state or "system" not in state:
            for widget in all_widgets:
                if widget:
                    widget.configure(state="disabled")
            self.temp_label.configure(text="- °C")
            return
        system_state = state.get("system", {})
        temp = system_state.get("temp", "-")
        self.temp_label.configure(text=f"{temp} °C")
        auto_mode_is_on = system_state.get("auto", False)
        if self.auto_mode_switch.get() != auto_mode_is_on:
            if auto_mode_is_on:
                self.auto_mode_switch.select()
            else:
                self.auto_mode_switch.deselect()
        self.auto_mode_switch.configure(state="normal")
        spraying = "Да" if system_state.get("spraying_active") else "Нет"
        self.spraying_label.configure(text=spraying, text_color="orange" if system_state.get("spraying_active") else "white")
        sensor_type = system_state.get("sensor_type", "N/A")
        sensor_error = system_state.get("temp_error", 0)
        http_err_count = system_state.get("http_error_count", 0)
        sensor_text = f"{str(sensor_type).upper()}"
        if str(sensor_type) == "remote" and http_err_count > 0:
            sensor_text += f" (ошибок: {http_err_count})"
        self.sensor_label.configure(text=sensor_text, text_color="red" if sensor_error else "white")
        num_fans = system_state.get("num_fans", 1)

        # --- Проверяем ошибки и показываем диалог, если они новые ---
        if self.app:
            if sensor_error and not self._last_known_error_state['temp_error']:
                self.app.show_notification(f"Ошибка: {self.device_name} ({self.device_info.get('location')})", f"Обнаружена проблема с датчиком температуры (код: {sensor_error}).")
            
            for i in range(1, num_fans + 1):
                fan_state = state.get(f"fan{i}", {})
                new_error_code = fan_state.get('error', 0)
                last_error_code = self._last_known_error_state[f'fan{i}_error']
                if new_error_code != 0 and new_error_code != last_error_code:
                    error_to_show = f"Устройство сообщило об ошибке. Код: {new_error_code}"
                    self.app.show_notification(f"Ошибка: {self.device_name} ({self.device_info.get('location')})", f"Вентилятор #{i}: {error_to_show}")
        
        self._last_known_error_state['temp_error'] = sensor_error
        for i in range(1, num_fans + 1):
            self._last_known_error_state[f'fan{i}_error'] = state.get(f"fan{i}", {}).get('error', 0)
        # --- Конец блока проверки ошибок ---

        if num_fans == 1:
            self.fan_2_frame.grid_remove()
        else:
            self.fan_2_frame.grid()
        for i in range(1, 3):
            fan_state = state.get(f"fan{i}", {})
            is_manual_mode = not auto_mode_is_on

            status_code = fan_state.get('status')
            status_text = self.STATUS_MAP.get(status_code, f"Код: {status_code or '--'}")
            getattr(self, f"fan_{i}_status_label").configure(text=f"Статус: {status_text}")
            
            error_code = fan_state.get('error', 0)
            err_msg = f"Код: {error_code}" if error_code != 0 else 'Нет'
            error_label = getattr(self, f"fan_{i}_error_label")
            error_label.configure(text=err_msg)
            if error_code != 0:
                error_label.configure(text_color="#F44336")
            else:
                error_label.configure(text_color="#9E9E9E")
            current_val = float(fan_state.get('current', 0.0))
            freq_val = float(fan_state.get('freq', 0.0))
            getattr(self, f"fan_{i}_current_label").configure(text=f"Ток: {current_val:.1f} A")
            getattr(self, f"fan_{i}_freq_label").configure(text=f"Частота: {(freq_val / 10.0):.1f} Hz")
            for btn in getattr(self, f"fan_{i}_control_buttons"):
                btn.configure(state="normal" if is_manual_mode else "disabled")
            getattr(self, f"fan_{i}_speed_slider").configure(state="normal" if is_manual_mode else "disabled")
            getattr(self, f"fan_{i}_speed_button").configure(state="normal" if is_manual_mode else "disabled")
