# -*- coding: utf-8 -*-
import json
import logging
import customtkinter as ctk
from datetime import datetime, timedelta
import os
import tkinter as tk
from .base_device import BaseController, BaseDeviceFrame
# Импортируем функции для работы с БД
import database_manager

logger = logging.getLogger(__name__)

class PumpController(BaseController):
    """
    Контроллер для устройства "Насос".
    Реализует парсинг сообщений и отправку команд согласно документации.
    Использует SQLite для хранения истории замеров.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._load_history_from_db(hours=1)

    def _load_history_from_db(self, hours: int = 1):
        """Загружает историю из БД за указанный период."""
        logger.info(f"Загрузка истории за {hours}ч для {self.device_ip} из БД...")
        self.state['current_sample_history'] = database_manager.get_history(self.device_ip, hours=hours)
        self.state['history_period_hours'] = hours
        logger.info(f"Загружено {len(self.state['current_sample_history'])} записей истории.")

    async def set_history_period(self, hours: int):
        """Загружает историю для нового периода и обновляет UI."""
        self._load_history_from_db(hours=hours)
        if self.state_update_callback:
            self.state_update_callback(self.state, 'connected')

    def _parse_message(self, message):
        try:
            data = json.loads(message)

            # Сохраняем важные переменные из *старого* состояния
            prev_pump_on = self.state.get("pumpOn", False)
            last_start_time = self.state.get("last_start_time")
            # Копируем историю, чтобы избежать проблем с мутацией состояния
            history = list(self.state.get("current_sample_history", []))

            # Если пришел новый замер, добавляем его в БД и в локальную историю
            if data.get("type") == "current_sample" and "value" in data:
                now = datetime.now()
                value = data.get("value")
                
                # 1. Добавляем в очередь на запись в БД (в фоне)
                database_manager.add_current_sample(self.device_ip, value)

                # 2. Обновляем локальную историю для немедленной отрисовки графика
                history.append((now, value))
                current_period_hours = self.state.get('history_period_hours', 1)
                period_ago = now - timedelta(hours=current_period_hours)
                history = [sample for sample in history if sample[0] >= period_ago]

            # Сохраняем выбранный период, чтобы он не потерялся при полном обновлении
            current_period = self.state.get('history_period_hours', 1)

            # Обновляем основное состояние
            if 'controlMode' in data:
                self.state = data # Полное обновление
            else:
                self.state.update(data) # Частичное обновление

            # Всегда устанавливаем историю и период в обновленное состояние
            self.state['current_sample_history'] = history
            self.state['history_period_hours'] = current_period

            # Обрабатываем время последнего запуска
            new_pump_on = self.state.get("pumpOn", False)
            if new_pump_on and not prev_pump_on:
                self.state["last_start_time"] = datetime.now()
            elif last_start_time:
                # Восстанавливаем время, если оно было в старом состоянии, но не в новом
                if "last_start_time" not in self.state:
                    self.state["last_start_time"] = last_start_time

            if self.state_update_callback:
                self.state_update_callback(self.state, 'connected')

        except json.JSONDecodeError as e:
            error_msg = f"Ошибка декодирования JSON: {e}\nПолучено: {message}"
            logger.info(error_msg)
            if self.state_update_callback:
                self.state_update_callback(self.state, 'error', error_msg)

    async def _send_pump_command(self, command, **kwargs):
        payload = {"cmd": command}
        payload.update(kwargs)
        await self._send_command(payload)

    async def manual_start(self): await self._send_pump_command("manual_start")
    async def manual_stop(self): await self._send_pump_command("manual_stop")
    async def manual_reverse(self): await self._send_pump_command("manual_reverse")
    async def reset_error(self): await self._send_pump_command("reset_error")
    async def set_mode(self, mode: int): await self._send_pump_command("set_mode", value=mode)
    async def set_speed(self, speed: int): await self._send_pump_command("set_speed", value=speed)
    async def set_auto_settings(self, run_time: int, stop_time: int, auto_speed: int):
        await self._send_pump_command("set_auto_settings", runTime=run_time, stopTime=stop_time, autoSpeed=auto_speed)


class PumpControlFrame(BaseDeviceFrame):
    MODES = ["Ручной", "Автоматический", "API", "Поплавки (2 датчика)", "Один поплавок (верхний)", "Запуск по расписанию, стоп по току"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._slider_is_being_set_programmatically = False
        self._animation_job = None
        self._animation_frames = ["|", "/", "-", "\\"]
        self._animation_frame_index = 0
        self._last_known_state = {}
        self._last_known_error_state = {'active': True, 'vfdError': 0}
        self._current_graph_hours = 1 
        self.graph_period_buttons = {}
        title_label = ctk.CTkLabel(self, text=self.device_name, font=ctk.CTkFont(size=20, weight="bold"))
        title_label.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="ew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(6, weight=1) # Место для графика

        self._create_status_widgets()
        self._create_control_widgets()
        self._create_graph_widgets()
        self.update_ui({}, "disconnected")

    def _create_status_widgets(self):
        frame = ctk.CTkFrame(self)
        frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        pump_status_frame = ctk.CTkFrame(frame, fg_color="transparent")
        pump_status_frame.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.pump_status_label = ctk.CTkLabel(pump_status_frame, text="Насос: --", font=ctk.CTkFont(size=14, weight="bold"))
        self.pump_status_label.pack(side="left")
        self.animation_label = ctk.CTkLabel(pump_status_frame, text="", width=10, font=ctk.CTkFont(size=14, weight="bold"))
        self.animation_label.pack(side="left", padx=(5, 0))

        self.vfd_status_label = ctk.CTkLabel(frame, text="ПЧ: --")
        self.vfd_status_label.grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.current_label = ctk.CTkLabel(frame, text="Ток: -- A")
        self.current_label.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        self.freq_label = ctk.CTkLabel(frame, text="Частота: -- Hz")
        self.freq_label.grid(row=1, column=1, padx=5, pady=2, sticky="w")
        self.float_high_label = ctk.CTkLabel(frame, text="Верх. попл: --")
        self.float_high_label.grid(row=0, column=2, padx=5, pady=2, sticky="w")
        self.float_low_label = ctk.CTkLabel(frame, text="Нижн. попл: --")
        self.float_low_label.grid(row=1, column=2, padx=5, pady=2, sticky="w")
        self.error_label = ctk.CTkLabel(frame, text="Ошибка: Нет", font=ctk.CTkFont(weight="bold"))
        self.error_label.grid(row=0, column=3, padx=5, pady=2, sticky="w")
        self.last_start_label = ctk.CTkLabel(frame, text="Посл. вкл: --")
        self.last_start_label.grid(row=1, column=3, padx=5, pady=2, sticky="w")

    def _create_control_widgets(self):
        mode_frame = ctk.CTkFrame(self)
        mode_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        mode_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(mode_frame, text="Режим работы:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10)
        self.mode_menu = ctk.CTkOptionMenu(mode_frame, values=self.MODES, command=self._on_mode_change)
        self.mode_menu.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.manual_frame = ctk.CTkFrame(self)
        self.manual_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        self.manual_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self.start_button = ctk.CTkButton(self.manual_frame, text="Старт", command=lambda: self.safe_async_call(self.controller.manual_start()))
        self.start_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.stop_button = ctk.CTkButton(self.manual_frame, text="Стоп", command=lambda: self.safe_async_call(self.controller.manual_stop()), fg_color="#D32F2F", hover_color="#B71C1C")
        self.stop_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.reverse_button = ctk.CTkButton(self.manual_frame, text="Реверс", command=lambda: self.safe_async_call(self.controller.manual_reverse()))
        self.reverse_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        speed_frame = ctk.CTkFrame(self.manual_frame)
        speed_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        speed_frame.grid_columnconfigure(0, weight=1)
        self.speed_slider = ctk.CTkSlider(speed_frame, from_=0, to=50, command=self._on_slider_move)
        self.speed_slider.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        self.speed_label = ctk.CTkLabel(speed_frame, text="Скорость: 25.0 Гц")
        self.speed_label.grid(row=0, column=1, padx=10)

        self.timer_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.timer_frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")
        self.timer_frame.grid_columnconfigure((0,1,2,3), weight=1)
        ctk.CTkLabel(self.timer_frame, text="Время работы (с):").grid(row=0, column=0, sticky="w")
        self.run_time_entry = ctk.CTkEntry(self.timer_frame, width=80)
        self.run_time_entry.grid(row=0, column=1, padx=5)
        ctk.CTkLabel(self.timer_frame, text="Время простоя (с):").grid(row=1, column=0, sticky="w")
        self.stop_time_entry = ctk.CTkEntry(self.timer_frame, width=80)
        self.stop_time_entry.grid(row=1, column=1, padx=5)
        ctk.CTkLabel(self.timer_frame, text="Скорость в авто (%):").grid(row=0, column=2, sticky="w")
        self.auto_speed_entry = ctk.CTkEntry(self.timer_frame, width=80)
        self.auto_speed_entry.grid(row=0, column=3, padx=5)
        self.save_timer_button = ctk.CTkButton(self.timer_frame, text="Сохранить настройки авто-режима", command=self._save_auto_settings)
        self.save_timer_button.grid(row=1, column=2, columnspan=2, pady=10, padx=5, sticky="ew")

        self.reset_button = ctk.CTkButton(self, text="Сброс ошибки ПЧ", command=lambda: self.safe_async_call(self.controller.reset_error()), fg_color="gray")
        self.reset_button.grid(row=5, column=0, padx=10, pady=10, sticky="ew")

    def _create_graph_widgets(self):
        graph_container = ctk.CTkFrame(self)
        graph_container.grid(row=6, column=0, columnspan=2, padx=10, pady=(10, 10), sticky="nsew")
        graph_container.grid_columnconfigure(0, weight=1)
        graph_container.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(graph_container, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,5))
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame, text="График тока", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w")
        
        button_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        button_frame.grid(row=0, column=1, sticky="e")

        for i, period in enumerate([1, 8, 24]):
            btn = ctk.CTkButton(
                button_frame, 
                text=f"{period}ч", 
                width=50,
                command=lambda p=period: self._set_graph_period(p)
            )
            btn.grid(row=0, column=i, padx=2)
            self.graph_period_buttons[period] = btn

        self.graph_frame = ctk.CTkFrame(graph_container, fg_color="#2B2B2B")
        self.graph_frame.grid(row=1, column=0, padx=10, pady=(0,10), sticky="nsew")

    def _set_graph_period(self, hours: int):
        """Вызывается при нажатии на кнопки периода."""
        if self._current_graph_hours == hours:
            return 
        
        logger.info(f"Запрос на изменение периода графика на {hours}ч.")
        self.safe_async_call(self.controller.set_history_period(hours))

    def _update_button_states(self):
        """Обновляет внешний вид кнопок периода."""
        for period, button in self.graph_period_buttons.items():
            if period == self._current_graph_hours:
                button.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"], state="disabled")
            else:
                button.configure(fg_color="gray", state="normal")

    def _on_mode_change(self, new_mode_str: str):
        try:
            current_mode_idx = self.controller.state.get("controlMode", -1)
            new_idx = self.MODES.index(new_mode_str)
            if current_mode_idx != new_idx:
                self.safe_async_call(self.controller.set_mode(new_idx))
        except (ValueError, AttributeError): pass

    def _on_slider_move(self, value):
        self.speed_label.configure(text=f"Скорость: {value:.1f} Гц")
        if not self._slider_is_being_set_programmatically:
            self.safe_async_call(self.controller.set_speed(int(value)))

    def _save_auto_settings(self):
        try:
            run_time = int(self.run_time_entry.get())
            stop_time = int(self.stop_time_entry.get())
            auto_speed = int(self.auto_speed_entry.get())
            self.safe_async_call(self.controller.set_auto_settings(run_time, stop_time, auto_speed))
        except ValueError:
            logger.error("Ошибка: введите корректные числовые значения для настроек таймера.")

    def _animate_pump(self):
        if self._animation_job:
            frame = self._animation_frames[self._animation_frame_index]
            self.animation_label.configure(text=frame)
            self._animation_frame_index = (self._animation_frame_index + 1) % len(self._animation_frames)
            self._animation_job = self.after(200, self._animate_pump)

    def _update_graph(self, history):
        self.graph_frame.update_idletasks()

        for widget in self.graph_frame.winfo_children():
            widget.destroy()

        # History - это список кортежей: (datetime, value)
        # Для отрисовки линии нужно как минимум 2 точки
        if not history or len(history) < 2:
            ctk.CTkLabel(self.graph_frame, text="Сбор данных для графика...").pack(expand=True)
            return

        graph_width = self.graph_frame.winfo_width()
        graph_height = self.graph_frame.winfo_height()

        if graph_width < 2 or graph_height < 2:
            # Если фрейм еще не отрисован, подождать и повторить
            self.after(100, lambda: self._update_graph(history))
            return

        canvas = tk.Canvas(self.graph_frame, bg="#2B2B2B", width=graph_width, height=graph_height, highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        # --- Расчет диапазонов данных ---
        now = datetime.now()
        start_time = now - timedelta(hours=self._current_graph_hours)
        time_delta_seconds = self._current_graph_hours * 3600.0

        values = [s[1] for s in history]
        max_val = max(values)
        min_val = min(values)
        val_range = (max_val - min_val) if max_val > min_val else 1.0

        # --- Отрисовка линии ---
        points = []
        for timestamp, value in history:
            # Рассчитываем координату X как пропорцию времени в выбранном окне
            if timestamp < start_time: continue # Пропускаем точки, которые выходят за рамки
            time_since_start = timestamp - start_time
            x_ratio = time_since_start.total_seconds() / time_delta_seconds
            x = x_ratio * graph_width

            # Рассчитываем координату Y с отступом 10px сверху и снизу
            y_ratio = (value - min_val) / val_range
            y = graph_height - (y_ratio * (graph_height - 20) + 10)

            points.extend([x, y])

        if len(points) >= 4:  # Нужно как минимум две пары (x,y)
            canvas.create_line(points, fill="#4CAF50", width=2)

        # --- Добавление меток ---
        font_small = ctk.CTkFont(size=10)
        canvas.create_text(5, 10, text=f"{max_val:.2f}A", anchor="w", fill="gray", font=font_small)
        canvas.create_text(5, graph_height - 10, text=f"{min_val:.2f}A", anchor="sw", fill="gray", font=font_small)

        canvas.create_text(10, graph_height/2, text=f"-{self._current_graph_hours}ч", anchor="w", fill="gray", font=font_small)
        canvas.create_text(graph_width - 10, graph_height/2, text="Сейчас", anchor="e", fill="gray", font=font_small)
        
        self._update_button_states()

    def update_ui(self, state, status):
        # 1. Обработка отключения
        if status != 'connected' or not state:
            if self._last_known_state.get('status') != 'disconnected':
                 self._disconnect_ui()
                 # Запоминаем, что мы в статусе "отключено"
                 self._last_known_state = {'status': 'disconnected'}
            return

        # 2. Обработка подключения (если до этого были отключены)
        # Принудительно обновляем все, если переподключились
        if not self._last_known_state or self._last_known_state.get('status') == 'disconnected':
            self._enable_all_controls(True)
            # Сбрасываем last_known_state, чтобы заставить UI полностью обновиться
            self._last_known_state = {} 

        # 3. Выход, если данные не изменились
        if state == self._last_known_state:
            return 

        old_state = self._last_known_state

        # 4. Обновление UI по частям (только то, что изменилось)
        
        # --- Проверяем ошибки устройства и показываем диалог, если они новые ---
        new_vfd_error = state.get("vfdError", 0)
        new_vfd_active = state.get("active", False)

        if self.app:
            # Ошибка ЧП (например, перегрузка)
            if new_vfd_error != 0 and new_vfd_error != self._last_known_error_state['vfdError']:
                self.app.show_notification(f"Ошибка: {self.device_name} ({self.device_info.get('location')})", f"Частотный преобразователь сообщил об ошибке. Код: {new_vfd_error}")
            
            # Потеря связи с ЧП
            if not new_vfd_active and self._last_known_error_state['active']:
                self.app.show_notification(f"Ошибка: {self.device_name} ({self.device_info.get('location')})", "Потеряна связь с частотным преобразователем (ПЧ).")
        
        self._last_known_error_state = {'active': new_vfd_active, 'vfdError': new_vfd_error}
        # --- Конец блока проверки ошибок ---

        pump_on = state.get("pumpOn", False)
        if pump_on != old_state.get("pumpOn"):
            if pump_on and not self._animation_job:
                self._animation_job = self.after(100, self._animate_pump)
            elif not pump_on and self._animation_job:
                self.after_cancel(self._animation_job)
                self._animation_job = None
                self.animation_label.configure(text="")
            self.pump_status_label.configure(text=f"Насос: {'ВКЛ' if pump_on else 'ВЫКЛ'}", text_color="#4CAF50" if pump_on else "#D32F2F")

        vfd_active = state.get("active", False)
        if vfd_active != old_state.get("active"):
            self.vfd_status_label.configure(text=f"ПЧ: {'На связи' if vfd_active else 'Нет связи'}", text_color="white" if vfd_active else "gray")
        
        if state.get('current') != old_state.get('current'):
            self.current_label.configure(text=f"Ток: {state.get('current', 0):.2f} A")

        if state.get('freq') != old_state.get('freq'):
            self.freq_label.configure(text=f"Частота: {state.get('freq', 0):.1f} Hz")

        float_high = state.get("floatHighActive", False)
        if float_high != old_state.get("floatHighActive"):
            self.float_high_label.configure(text=f"Верх. попл: {'СРАБОТАЛ' if float_high else 'Норма'}", text_color="orange" if float_high else "white")

        float_low = state.get("floatLowActive", False)
        if float_low != old_state.get("floatLowActive"):
            self.float_low_label.configure(text=f"Нижн. попл: {'СРАБОТАЛ' if float_low else 'Норма'}", text_color="orange" if float_low else "white")

        error_code = state.get("vfdError", 0)
        if error_code != old_state.get("vfdError"):
            self.error_label.configure(text=f"Ошибка: {error_code if error_code != 0 else 'Нет'}", text_color="#F44336" if error_code != 0 else "white")

        last_start_time = state.get("last_start_time")
        if last_start_time != old_state.get("last_start_time"):
            if last_start_time:
                time_str = last_start_time.strftime("%H:%M:%S %d.%m")
                self.last_start_label.configure(text=f"Посл. вкл: {time_str}")
            else:
                self.last_start_label.configure(text="Посл. вкл: --", text_color="gray")

        current_mode_idx = state.get("controlMode", 0)
        if current_mode_idx != old_state.get("controlMode"):
            idx_to_set = current_mode_idx if 0 <= current_mode_idx < len(self.MODES) else 0
            try:
                current_text = self.mode_menu.get()
                current_idx = self.MODES.index(current_text)
            except ValueError:
                current_idx = -1
            if current_idx != idx_to_set:
                self.mode_menu.set(self.MODES[idx_to_set])

            # Показываем/скрываем информацию о поплавках в зависимости от режима
            if current_mode_idx in [3, 4]: # "Поплавки (2 датчика)", "Один поплавок (верхний)"
                self.float_high_label.grid()
                self.float_low_label.grid()
            else:
                self.float_high_label.grid_remove()
                self.float_low_label.grid_remove()

            is_manual_mode = current_mode_idx == 0
            is_timer_mode = current_mode_idx == 1
            for widget in [self.start_button, self.stop_button, self.reverse_button, self.speed_slider]:
                widget.configure(state="normal" if is_manual_mode else "disabled")
            if is_timer_mode:
                self.timer_frame.grid()
            else:
                self.timer_frame.grid_remove()

        if state.get("runTime") != old_state.get("runTime"):
            self.run_time_entry.delete(0, "end"); self.run_time_entry.insert(0, str(state.get("runTime", 0)))
        if state.get("stopTime") != old_state.get("stopTime"):
            self.stop_time_entry.delete(0, "end"); self.stop_time_entry.insert(0, str(state.get("stopTime", 0)))
        if state.get("autoModeSpeed") != old_state.get("autoModeSpeed"):
            self.auto_speed_entry.delete(0, "end"); self.auto_speed_entry.insert(0, str(state.get("autoModeSpeed", 50)))

        # Обновляем слайдер только если значение изменилось
        if state.get("targetSpeed") != old_state.get("targetSpeed"):
            try:
                slider_value = float(state.get("targetSpeed", 25))
            except (ValueError, TypeError):
                slider_value = 25.0
            
            self._slider_is_being_set_programmatically = True
            self.speed_slider.set(slider_value)
            self._slider_is_being_set_programmatically = False
            self.speed_label.configure(text=f"Скорость: {slider_value:.1f} Гц")

        # Обновляем график только при изменении истории или периода
        if (state.get("current_sample_history") != old_state.get("current_sample_history") or
            state.get("history_period_hours") != old_state.get("history_period_hours")):
            self._current_graph_hours = state.get("history_period_hours", 1)
            history = state.get("current_sample_history", [])
            self._update_graph(history)

        # Наконец, сохраняем текущее состояние как "последнее известное"
        self._last_known_state = state.copy()

    def _disconnect_ui(self):
        """Отключает и сбрасывает все элементы UI."""
        if self._animation_job:
            self.after_cancel(self._animation_job)
            self._animation_job = None
            self.animation_label.configure(text="")
        self.pump_status_label.configure(text="Насос: --", text_color="gray")
        self.vfd_status_label.configure(text="ПЧ: --", text_color="gray")
        self.current_label.configure(text="Ток: -- A", text_color="gray")
        self.freq_label.configure(text="Частота: -- Hz", text_color="gray")
        self.float_high_label.configure(text="Верх. попл: --", text_color="gray")
        self.float_low_label.configure(text="Нижн. попл: --", text_color="gray")
        self.error_label.configure(text="Ошибка: Нет", text_color="gray")
        self.last_start_label.configure(text="Посл. вкл: --", text_color="gray")
        self._enable_all_controls(False)
        self._update_graph([]) # Очищаем график

    def _enable_all_controls(self, enable: bool):
        """Включает или отключает все элементы управления."""
        all_controls = [self.mode_menu, self.start_button, self.stop_button, self.reverse_button, self.speed_slider, self.run_time_entry, self.stop_time_entry, self.auto_speed_entry, self.save_timer_button, self.reset_button]
        for widget in all_controls:
            # Некоторые виджеты могут быть уничтожены, поэтому нужна проверка
            if widget and widget.winfo_exists():
                widget.configure(state="normal" if enable else "disabled")