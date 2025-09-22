# -*- coding: utf-8 -*-
import sqlite3
import threading
import queue
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DB_FILE = "scada_history.db"
_write_queue = queue.Queue()
_stop_event = threading.Event()
_db_connection = None
_db_writer_thread = None

def _db_writer():
    """
    Функция, работающая в отдельном потоке.
    Получает данные из очереди и записывает их в базу данных.
    """
    # Создаем собственное соединение для этого потока
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    logger.info("Поток записи в БД запущен.")
    while not _stop_event.is_set() or not _write_queue.empty():
        try:
            # Ждем новую запись не более 1 секунды
            sql, params = _write_queue.get(timeout=1)
            cursor.execute(sql, params)
            conn.commit()
            _write_queue.task_done()
        except queue.Empty:
            continue
        except sqlite3.Error as e:
            logger.info(f"Ошибка записи в БД: {e}")
    conn.close()
    logger.info("Поток записи в БД остановлен.")

def setup_database():
    """
    Настраивает базу данных: создает таблицу и запускает поток для записи.
    Вызывается один раз при старте приложения.
    """
    global _db_connection, _db_writer_thread
    try:
        _db_connection = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = _db_connection.cursor()
        # Создаем таблицу, если она не существует
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS current_history (
                device_ip TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                value REAL NOT NULL,
                PRIMARY KEY (device_ip, timestamp)
            )
        """)
        _db_connection.commit()
        logger.info("База данных успешно настроена.")
        
        # Запускаем фоновый поток для записи
        if _db_writer_thread is None or not _db_writer_thread.is_alive():
            _stop_event.clear()
            _db_writer_thread = threading.Thread(target=_db_writer, daemon=True)
            _db_writer_thread.start()

    except sqlite3.Error as e:
        logger.info(f"Критическая ошибка при настройке БД: {e}")
        _db_connection = None

def add_current_sample(device_ip: str, value: float):
    """
    Добавляет новый замер тока в очередь на запись в БД.
    """
    if _db_connection is None:
        return
    
    timestamp = datetime.now().isoformat()
    sql = "INSERT INTO current_history (device_ip, timestamp, value) VALUES (?, ?, ?)"
    params = (device_ip, timestamp, value)
    _write_queue.put((sql, params))

def get_history(device_ip: str, hours: int = 1):
    """
    Получает историю замеров для конкретного устройства за указанный период.
    """
    if _db_connection is None:
        return []
        
    history = []
    try:
        cursor = _db_connection.cursor()
        one_hour_ago = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute(
            "SELECT timestamp, value FROM current_history WHERE device_ip = ? AND timestamp >= ? ORDER BY timestamp ASC",
            (device_ip, one_hour_ago)
        )
        # Конвертируем обратно в кортежи (datetime, value)
        history = [(datetime.fromisoformat(ts), val) for ts, val in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.info(f"Ошибка получения истории из БД для {device_ip}: {e}")
    
    return history

def close_database():
    """
    Корректно останавливает поток записи и закрывает соединение с БД.
    """
    logger.info("Закрытие соединений с БД...")
    _stop_event.set()
    if _db_writer_thread:
        _db_writer_thread.join(timeout=5) # Ждем завершения потока
    if _db_connection:
        _db_connection.close()
    logger.info("Соединения с БД закрыты.") 