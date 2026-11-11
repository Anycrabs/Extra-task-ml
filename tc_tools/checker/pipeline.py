"""Конвейер модуля проверки: чтение → запуск → агрегирование → отчёты.

::

    файлы решений ──parse──► задания ──run──► результаты ТК ──aggregate──► статусы
                                                                     │
                     _all.log, _tc_all.log, _tc_failed.log, _results.xlsx, _dashboard.html
"""

from __future__ import annotations

import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..common.constants import FAILED, PASSED
from ..common.discovery import collect_files
from ..common.logsetup import close_logger, say, setup_logger
from ..common.naming import make_timestamp, report_name
from ..common.parser import load_solution_file
from ..common.textio import write_text
from .dashboard import render_dashboard
from .reports import brief_report, detailed_report, file_sort_key, filter_files, write_results_xlsx
from .runner import check_task

DEFAULTS = {
    "inputs": [],               # файлы решений и/или папки с ними
    "recursive": False,         # искать файлы во вложенных папках
    "input_eol": "auto",        # формат переводов строк во входных файлах: auto|crlf|lf|cr
    "output_eol": "crlf",       # формат переводов строк в создаваемых файлах: crlf|lf|cr
    "timeout": 5.0,             # ограничение времени на один ТК, секунд
    "jobs": 4,                  # число заданий, проверяемых параллельно
    "python": None,             # интерпретатор для запуска решений (по умолчанию текущий)
    "reports_dir": "reports",   # папка для отчётов
    "log_dir": "logs",          # папка для логов
    "xlsx": True,               # создавать сводный отчёт _results.xlsx
    "dashboard": True,          # создавать HTML-дашборд _dashboard.html
    "tc_all_skip_passed": False,  # не включать в _tc_all.log файлы без ошибок
    "groups": [],               # фильтр сводного отчёта и дашборда: группы
    "students": [],             # фильтр: студенты (ФамилияИО)
    "file_numbers": [],         # фильтр: номера файлов с заданиями
}


def validate_settings(settings: dict) -> None:
    """Проверяет значения настроек модуля проверки.

    Args:
        settings: Настройки после :func:`common.config.load_settings`.

    Raises:
        ValueError: Недопустимое значение параметра.
    """
    if float(settings["timeout"]) <= 0:
        raise ValueError("timeout должен быть положительным числом")
    if int(settings["jobs"]) < 1:
        raise ValueError("jobs должен быть не меньше 1")
    for number in settings["file_numbers"]:
        if not str(number).strip().isdigit():
            raise ValueError(f"file_numbers: «{number}» не является номером файла")


def _broken_result(broken: dict) -> dict:
    """Результат для задания с ошибкой оформления: не выполняется, статус FAILED."""
    return {"id": broken["id"], "file_no": broken["file_no"], "number": broken["number"],
            "title": None, "solution": None, "test_cases": [], "tc_results": [],
            "status": FAILED, "format_error": broken["error"]}


def check_files(files: list[dict], settings: dict, log: logging.Logger) -> list[dict]:
    """Проверяет все задания всех файлов и вычисляет статусы файлов.

    Задания проверяются параллельно в пуле потоков (каждый поток лишь ждёт
    дочерний процесс Python, поэтому GIL не мешает). ``pool.map`` возвращает
    результаты в исходном порядке, поэтому отчёты детерминированы.

    Args:
        files: Разобранные файлы решений.
        settings: Настройки модуля.
        log: Логгер.

    Returns:
        Проверенные файлы: ``tasks`` содержат результаты проверки (включая задания
        с ошибкой оформления как FAILED), добавлен ``status`` файла.
    """
    python = settings["python"] or sys.executable
    timeout = float(settings["timeout"])
    jobs = [(index, task) for index, item in enumerate(files) for task in item["tasks"]]
    per_file = [[_broken_result(broken) for broken in item["broken"]] for item in files]

    def worker(task: dict) -> dict:
        """Проверяет одно задание с текущими настройками (для ``pool.map``)."""
        return check_task(task, timeout, python)

    with ThreadPoolExecutor(max_workers=int(settings["jobs"])) as pool:
        results = pool.map(worker, [task for _, task in jobs])
        for done, ((index, _), result) in enumerate(zip(jobs, results), start=1):
            name = files[index]["name"]
            tc_results = result["tc_results"]
            if not tc_results:
                log.warning("%s, задание %s: нет тест-кейсов — статус FAILED", name, result["id"])
            for item in tc_results:
                if item["status"] == FAILED:
                    log.debug("%s, задание %s, ТК-%d: %s", name, result["id"], item["number"], item["reason"])
            passed = sum(item["status"] == PASSED for item in tc_results)
            say(log, f"[{done}/{len(jobs)}] {name} → {result['id']}: {result['status']} "
                     f"(ТК {passed}/{len(tc_results)})")
            per_file[index].append(result)

    checked = []
    for item, tasks in zip(files, per_file):
        tasks.sort(key=lambda task: task["number"])
        all_passed = bool(tasks) and all(task["status"] == PASSED for task in tasks)
        checked.append({**item, "tasks": tasks, "status": PASSED if all_passed else FAILED})
    return checked


def write_reports(checked: list[dict], settings: dict, timestamp: str, log: logging.Logger) -> list[Path]:
    """Создаёт все отчёты модуля проверки.

    Краткий и подробные отчёты всегда содержат все проверенные файлы (краткий
    отчёт нужен модулю форматирования). Фильтры по группам, студентам и номерам
    файлов применяются к сводному xlsx-отчёту и дашборду.

    Args:
        checked: Проверенные файлы.
        settings: Настройки модуля.
        timestamp: Метка времени запуска.
        log: Логгер.

    Returns:
        Пути к созданным файлам.
    """
    folder = Path(settings["reports_dir"])
    eol = settings["output_eol"]
    created = [
        write_text(folder / report_name(timestamp, "all.log"), brief_report(checked), eol),
        write_text(folder / report_name(timestamp, "tc_all.log"),
                   detailed_report(checked, skip_passed_files=settings["tc_all_skip_passed"]), eol),
        write_text(folder / report_name(timestamp, "tc_failed.log"),
                   detailed_report(checked, only_failed=True), eol),
    ]
    selected = filter_files(checked, settings["groups"], settings["students"], settings["file_numbers"])
    if len(selected) != len(checked):
        log.info("Фильтр сводного отчёта: отобрано файлов %d из %d", len(selected), len(checked))
    if settings["xlsx"]:
        try:
            created.append(write_results_xlsx(selected, folder / report_name(timestamp, "results.xlsx")))
        except OSError as exc:
            log.error("Не удалось сохранить сводный отчёт xlsx: %s", exc)
    if settings["dashboard"]:
        created.append(write_text(folder / report_name(timestamp, "dashboard.html"),
                                  render_dashboard(selected, timestamp), eol))
    return created


def _execute(settings: dict, timestamp: str, log: logging.Logger) -> int:
    """Основная логика запуска (без настройки и закрытия лога)."""
    say(log, f"Модуль проверки тест-кейсов, метка времени {timestamp}")
    paths = collect_files(settings["inputs"], recursive=settings["recursive"], log=log)
    if not paths:
        log.error("Не найдено ни одного файла решений")
        return 1

    files = []
    for path in paths:
        loaded, _ = load_solution_file(path, settings["input_eol"], log)
        if loaded is not None:
            files.append(loaded)
    rejected = len(paths) - len(files)
    if not files:
        log.error("Нет корректных файлов решений для проверки")
        return 1
    files.sort(key=file_sort_key)

    checked = check_files(files, settings, log)
    created = write_reports(checked, settings, timestamp, log)

    tasks = [task for item in checked for task in item["tasks"]]
    passed = sum(task["status"] == PASSED for task in tasks)
    say(log, "")
    say(log, "Итоги проверки:")
    say(log, f"  файлов решений: {len(paths)} (проверено {len(files)}, не обработано {rejected})")
    say(log, f"  заданий: {len(tasks)}, верно: {passed}, неверно: {len(tasks) - passed}")
    say(log, "  созданные отчёты:")
    for path in created:
        say(log, f"    {path}")
    return 0


def run(settings: dict) -> int:
    """Запускает модуль проверки с готовыми настройками.

    Args:
        settings: Настройки (см. :data:`DEFAULTS`).

    Returns:
        Код завершения: 0 — успешно, 1 — ошибка.
    """
    timestamp = make_timestamp()
    log, log_path = setup_logger("tc_tools.checker", settings["log_dir"], "Check_log",
                                 timestamp, settings["output_eol"])
    try:
        code = _execute(settings, timestamp, log)
    except Exception:  # noqa: BLE001 — любую непредвиденную ошибку фиксируем в логе
        log.exception("Непредвиденная ошибка")
        code = 1
    say(log, f"Лог: {log_path}")
    close_logger(log)
    return code
