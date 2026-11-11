"""Чтение кратких отчётов модуля проверки ``Отчет_<Метка>_all.log``.

Если отчётов несколько, они применяются в порядке возрастания метки времени:
результат более поздней проверки задания заменяет более ранний. Так для каждого
задания используется результат самой поздней проверки, а задания, проверенные
только в более старых запусках, не теряются.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from ..common.constants import FAILED, PASSED
from ..common.naming import BRIEF_REPORT_RE, format_task_id, parse_task_id
from ..common.textio import read_lines

FILE_LINE_RE = re.compile(rf"(\d+):\s*({PASSED}|{FAILED})")
TASK_LINE_RE = re.compile(rf"\s+(\d+-\d+):\s*({PASSED}|{FAILED})")


def collect_report_files(paths: list[str], log: logging.Logger) -> list[tuple[str, Path]]:
    """Находит краткие отчёты по списку файлов и папок.

    В папках берутся только файлы, имя которых точно соответствует шаблону
    ``Отчет_<ГГГГММДД-ЧЧММСС>_all.log`` (отчёты ``_tc_all.log`` не подходят).

    Args:
        paths: Пути к файлам отчётов и/или папкам.
        log: Логгер.

    Returns:
        Список пар (метка времени, путь), отсортированный по метке времени.
    """
    found: dict[Path, str] = {}
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            candidates = sorted(path.iterdir())
        elif path.is_file():
            candidates = [path]
            if not BRIEF_REPORT_RE.fullmatch(path.name):
                log.error("%s: имя не соответствует шаблону Отчет_<Метка времени>_all.log — "
                          "отчёт пропущен", path.name)
                continue
        else:
            log.error("Путь к отчётам не найден: %s", path)
            continue
        for candidate in candidates:
            match = BRIEF_REPORT_RE.fullmatch(candidate.name)
            if match and candidate.is_file():
                found[candidate.resolve()] = match["timestamp"]
    return sorted(((stamp, path) for path, stamp in found.items()), key=lambda pair: (pair[0], str(pair[1])))


def parse_brief_report(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    """Разбирает строки краткого отчёта.

    Args:
        lines: Строки отчёта.

    Returns:
        Пара (словарь «номер задания → статус», список нераспознанных строк).
    """
    statuses: dict[str, str] = {}
    unknown: list[str] = []
    for line in lines:
        if not line.strip() or FILE_LINE_RE.fullmatch(line.rstrip()):
            continue
        match = TASK_LINE_RE.fullmatch(line.rstrip())
        if match:
            statuses[format_task_id(*parse_task_id(match[1]))] = match[2]
        else:
            unknown.append(line)
    return statuses, unknown


def load_statuses(paths: list[str], eol_mode: str, log: logging.Logger) -> dict[str, str]:
    """Загружает статусы заданий из всех найденных отчётов.

    Args:
        paths: Пути к файлам отчётов и/или папкам.
        eol_mode: Допустимый формат переводов строк во входных файлах.
        log: Логгер.

    Returns:
        Словарь «номер задания → статус» по результатам самой поздней проверки.
    """
    reports = collect_report_files(paths, log)
    if not reports:
        log.error("Не найдено ни одного краткого отчёта Отчет_<Метка времени>_all.log — "
                  "все задания будут исключены как отсутствующие в отчёте")
        return {}
    merged: dict[str, str] = {}
    for timestamp, path in reports:
        try:
            lines = read_lines(path, eol_mode)
        except (OSError, ValueError) as exc:
            log.error("%s: не удалось прочитать отчёт (%s) — отчёт пропущен", path.name, exc)
            continue
        statuses, unknown = parse_brief_report(lines)
        for line in unknown:
            log.warning("%s: нераспознанная строка «%s»", path.name, line.strip())
        merged.update(statuses)
        log.info("Прочитан отчёт %s (метка %s): заданий — %d", path.name, timestamp, len(statuses))
    return merged
