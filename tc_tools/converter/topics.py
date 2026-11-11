"""Справочник тем: CSV в UTF-8, разделитель ``;``, заголовок ``Номер темы;Название темы``."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from ..common.textio import read_lines

HEADER = ["Номер темы", "Название темы"]


def load_topics(path: str | Path, eol_mode: str, log: logging.Logger) -> dict[str, str] | None:
    """Загружает справочник тем.

    Номер темы сохраняется как строка без пробелов по краям. При повторе номера
    используется первое вхождение (с предупреждением в логе).

    Args:
        path: Путь к CSV-файлу.
        eol_mode: Допустимый формат переводов строк во входных файлах.
        log: Логгер.

    Returns:
        Словарь «номер темы → название» или ``None``, если файл не найден или
        не соответствует формату (модуль работает так, будто справочник не задан).
    """
    try:
        lines = read_lines(path, eol_mode)
    except (OSError, ValueError) as exc:
        log.error("Справочник тем %s не прочитан (%s) — используются только номера тем", path, exc)
        return None

    numbered = [(line_no, line) for line_no, line in enumerate(lines, start=1) if line.strip()]
    rows = list(csv.reader([line for _, line in numbered], delimiter=";"))
    if not rows or [cell.strip() for cell in rows[0]] != HEADER:
        log.error("Справочник тем %s: ожидалась строка заголовков «%s» — "
                  "используются только номера тем", path, ";".join(HEADER))
        return None

    topics: dict[str, str] = {}
    for (line_no, _), row in zip(numbered[1:], rows[1:]):
        if len(row) != 2:
            log.error("Справочник тем %s, строка %d: ожидалось 2 поля через «;», получено %d — "
                      "используются только номера тем", path, line_no, len(row))
            return None
        number, title = row[0].strip(), row[1].strip()
        if number in topics:
            log.warning("Справочник тем, строка %d: номер темы %s повторяется — "
                        "используется первое вхождение", line_no, number)
            continue
        topics[number] = title
    log.info("Справочник тем %s: загружено тем — %d", path, len(topics))
    return topics


def topic_title(topics: dict[str, str] | None, number: str, log: logging.Logger) -> str | None:
    """Определяет название темы по номеру.

    Args:
        topics: Справочник тем или ``None``, если он не задан.
        number: Номер темы (номер файла с заданиями).
        log: Логгер.

    Returns:
        Название темы или ``None``, если оно не определено.
    """
    if topics is None:
        return None
    title = topics.get(number.strip())
    if title is None:
        log.warning("Тема %s отсутствует в справочнике тем — используется только номер", number)
    elif not title:
        log.warning("Тема %s: пустое название в справочнике — используется только номер", number)
    return title or None
