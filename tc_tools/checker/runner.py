"""Запуск решения на тест-кейсах и сравнение фактического вывода с эталоном.

ВНИМАНИЕ: код решений выполняется без изоляции (как обычный Python-скрипт).
Модуль предназначен для личного использования; перед запуском просмотрите
решения на наличие необратимых действий.

Каждый тест-кейс выполняется в отдельном процессе интерпретатора. Текущая
папка процесса — временная папка задания, которая удаляется после проверки,
поэтому файлы, созданные решением «рядом с собой», не засоряют проект.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

from ..common.constants import FAILED, PASSED
from ..common.textio import normalize_eol

# Причины результата тест-кейса (поле ``reason``).
REASON_OK = "ok"
REASON_MISMATCH = "mismatch"
REASON_ERROR = "error"
REASON_TIMEOUT = "timeout"


def output_lines(text: str) -> list[str]:
    """Разбивает вывод на строки для сравнения.

    Любой формат переводов строк (CRLF, LF, CR) считается одинаковым;
    один завершающий перевод строки после последней строки игнорируется.

    Args:
        text: Вывод программы или эталон.

    Returns:
        Список строк. Пустой вывод и вывод ``"\\n"`` дают одинаковый результат ``[""]``.
    """
    normalized = normalize_eol(text)
    if normalized.endswith("\n"):
        normalized = normalized[:-1]
    return normalized.split("\n")


def compare_output(actual: str, expected: str) -> bool:
    """Сравнивает фактический вывод с эталоном построчно, без модификации значений.

    Пробелы, регистр, формат чисел не нормализуются: ``"5 "`` ≠ ``"5"``,
    ``"5.0"`` ≠ ``"5"``.

    Args:
        actual: Фактический вывод решения.
        expected: Эталон из тест-кейса.

    Returns:
        ``True``, если вывод совпадает с эталоном.
    """
    return output_lines(actual) == output_lines(expected)


def _decode(data: bytes | None) -> str:
    """Декодирует вывод процесса из UTF-8, заменяя некорректные байты."""
    return data.decode("utf-8", errors="replace") if data else ""


def run_test_case(
    script: Path, stdin_text: str, expected: str, timeout: float, python: str
) -> dict:
    """Запускает решение на одном тест-кейсе и сравнивает вывод с эталоном.

    Перед подачей в стандартный ввод переводы строк во входных значениях
    приводятся к ``\\n``. Процесс запускается с ``-X utf8``, чтобы ввод-вывод
    шёл в UTF-8 независимо от настроек ОС.

    Args:
        script: Путь к файлу с кодом решения.
        stdin_text: Входные значения тест-кейса.
        expected: Эталон.
        timeout: Ограничение времени выполнения, секунд.
        python: Путь к интерпретатору Python.

    Returns:
        Словарь ``{"status", "reason", "actual", "error", "duration"}``:
        ``status`` — PASSED/FAILED, ``reason`` — ok/mismatch/error/timeout,
        ``actual`` — фактический вывод, ``error`` — traceback или сообщение
        о превышении времени (``None``, если ошибки не было).
    """
    data = normalize_eol(stdin_text)
    if data and not data.endswith("\n"):
        data += "\n"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [python, "-X", "utf8", str(script)],
            input=data.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
            cwd=script.parent,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": FAILED,
            "reason": REASON_TIMEOUT,
            "actual": _decode(exc.stdout),
            "error": f"Превышено ограничение времени выполнения ({timeout:g} с)",
            "duration": timeout,
        }
    duration = time.perf_counter() - started
    actual = _decode(completed.stdout)

    if completed.returncode != 0:
        # Убираем из traceback путь к временной папке — остаётся только имя файла.
        error = _decode(completed.stderr).replace(str(script), script.name).strip()
        return {
            "status": FAILED,
            "reason": REASON_ERROR,
            "actual": actual,
            "error": error or f"Процесс завершился с кодом {completed.returncode}",
            "duration": duration,
        }
    matched = compare_output(actual, expected)
    return {
        "status": PASSED if matched else FAILED,
        "reason": REASON_OK if matched else REASON_MISMATCH,
        "actual": actual,
        "error": None,
        "duration": duration,
    }


def check_task(task: dict, timeout: float, python: str) -> dict:
    """Проверяет задание: запускает решение на каждом тест-кейсе.

    Код решения записывается во временную папку один раз и запускается
    отдельным процессом для каждого тест-кейса.

    Args:
        task: Задание (результат :func:`common.parser.parse_task_block`).
        timeout: Ограничение времени на один тест-кейс, секунд.
        python: Путь к интерпретатору Python.

    Returns:
        Копия задания с ключами ``status`` (PASSED/FAILED) и ``tc_results`` —
        списком результатов ``{"number", "input", "expected", "status", "reason",
        "actual", "error", "duration"}``. Задание без тест-кейсов — FAILED.
    """
    results = []
    with tempfile.TemporaryDirectory(prefix="tc_", ignore_cleanup_errors=True) as workdir:
        script = Path(workdir) / f"solution_{task['id']}.py"
        script.write_text(task["solution"] + "\n", encoding="utf-8")
        for case in task["test_cases"]:
            outcome = run_test_case(script, case["input"], case["output"], timeout, python)
            results.append({"number": case["number"], "input": case["input"],
                            "expected": case["output"], **outcome})
    all_passed = bool(results) and all(item["status"] == PASSED for item in results)
    return {**task, "status": PASSED if all_passed else FAILED, "tc_results": results}
