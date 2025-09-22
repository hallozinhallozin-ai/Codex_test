# Repository Guidelines

## Project Structure & Module Organization
The GUI entry point lives in `main.py`, wiring CustomTkinter views, websocket listeners, and dispatchers for pumps, fans, and curtains. `database_manager.py` keeps `scada_history.db` aligned with telemetry. Device behaviours reside in `devices/`, with `base_device.py` defining the control contract and concrete adapters like `pump.py`, `fan.py`, and `curtain.py`. Runtime settings come from `config.json`; protocol notes stay in `WEBSOCKET_USAGE.md`. Large telemetry archives (`pump_history_*.json`, `scada_1_backup_*.zip`) should remain untracked after regeneration.

## Build, Test, and Development Commands
Ensure Python 3.11+ is installed.
- `python -m venv .venv` and `.venv\Scripts\Activate.ps1` to create and enter the virtual environment.
- `pip install -r requirements.txt` to sync GUI, websocket, serial, and Telegram dependencies.
- `python main.py` to launch the operator console using endpoints defined in `config.json`.
- Back up `scada_history.db` before iterating on persistence (e.g., `copy scada_history.db scada_history_<timestamp>.db`).

## Coding Style & Naming Conventions
Use four-space indentation, `snake_case` for functions, `PascalCase` for classes, and uppercase constants for topics or pin IDs. Keep modules below 400 lines by extracting shared helpers. Reuse existing logging utilities instead of ad-hoc `print` calls. Add type hints when APIs cross modules and document new CustomTkinter widgets with short docstrings.

## Testing Guidelines
Adopt `pytest` for new coverage placed under a `tests/` package that mirrors `devices`. Name files `test_<module>.py` and store reusable payloads in `tests/fixtures/`. Run `pytest` plus a targeted manual GUI session covering any device you touched. Attach brief screen recordings when altering operator workflows.

## Commit & Pull Request Guidelines
Write commits in the imperative mood (`Add pump alarm debouncing`) and keep scope tight. Reference task IDs or incident numbers in the body. PRs need an impact summary, manual verification list (`python main.py`, `pytest`), and screenshots or telemetry snippets when behaviour changes. Highlight configuration edits and include the sanitised diff.


## Расширяемость устройств
Добавляйте новые типы через `services/device_registry.py`: вызовите `register_device_type` в инициализации собственного модуля и предоставьте контроллер, фрейм и фабрику URI. Конфигурация (`config.json`) валидируется автоматически — убедитесь, что поле `type` совпадает с зарегистрированным идентификатором, иначе `ConfigManager` откатит файл. Внутри `ui/app.py` доступны определения через `registry.require(...)`, поэтому расширения подключаются без правок монолита.
## Configuration & Data Safety
Treat `config.json` and `telegram_config.json` as environment-specific; scrub secrets before sharing. Work on copies of `scada_history.db` and archive raw telemetry outside source control. When adding device types, include a redacted config example in PR notes so operators can roll out safely.

