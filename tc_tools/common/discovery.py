"""Поиск входных файлов по списку путей (файлы и/или папки)."""

from __future__ import annotations

import logging
from pathlib import Path


def collect_files(
    paths: list[str],
    pattern: str = "*.txt",
    recursive: bool = False,
    log: logging.Logger | None = None,
) -> list[Path]:
    """Собирает список файлов из указанных путей.

    Файл берётся как есть, из папки берутся файлы, подходящие под ``pattern``
    (с подпапками, если ``recursive``). Повторы исключаются, порядок сохраняется:
    сначала в порядке перечисления путей, внутри папки — по алфавиту.

    Args:
        paths: Пути к файлам и папкам.
        pattern: Glob-шаблон для отбора файлов в папках.
        recursive: Искать ли файлы во вложенных папках.
        log: Логгер для сообщений о несуществующих путях.

    Returns:
        Список путей к найденным файлам.
    """
    found: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            matches = path.rglob(pattern) if recursive else path.glob(pattern)
            candidates = sorted(item for item in matches if item.is_file())
        elif path.is_file():
            candidates = [path]
        else:
            if log:
                log.error("Путь не найден: %s", path)
            continue
        for candidate in candidates:
            key = candidate.resolve()
            if key not in seen:
                seen.add(key)
                found.append(candidate)
    return found
