"""Чтение и запись текстовых файлов в UTF-8 с контролем формата переводов строк.

Поддерживаемые форматы: ``crlf`` (\\r\\n), ``lf`` (\\n), ``cr`` (\\r).
Для входных файлов дополнительно допускается режим ``auto`` — любые форматы,
в том числе смешанные в одном файле.

Внутри программы весь текст хранится с переводами строк ``\\n``; нужный формат
применяется только при записи файла.
"""

from __future__ import annotations

import re
from pathlib import Path

EOL_CHARS = {"crlf": "\r\n", "lf": "\n", "cr": "\r"}
INPUT_EOL_MODES = ("auto", "crlf", "lf", "cr")
OUTPUT_EOL_MODES = ("crlf", "lf", "cr")

# Порядок альтернатив важен: \r\n должен распознаваться раньше одиночного \r.
_ANY_EOL = re.compile(r"\r\n|\r|\n")
_EOL_NAMES = {"\r\n": "crlf", "\n": "lf", "\r": "cr"}


def detect_eol_kinds(text: str) -> set[str]:
    """Определяет, какие форматы переводов строк встречаются в тексте.

    Args:
        text: Исходный текст без какой-либо нормализации.

    Returns:
        Множество названий форматов (``crlf``, ``lf``, ``cr``); пустое, если
        в тексте нет переводов строк.
    """
    return {_EOL_NAMES[match.group()] for match in _ANY_EOL.finditer(text)}


def split_lines(text: str, eol_mode: str = "auto") -> list[str]:
    """Разбивает текст на строки с учётом допустимого формата переводов строк.

    Args:
        text: Исходный текст.
        eol_mode: ``auto`` — допускаются любые форматы; ``crlf``/``lf``/``cr`` —
            допускается только указанный.

    Returns:
        Список строк без символов перевода строки. Если текст оканчивается
        переводом строки, последний элемент — пустая строка.

    Raises:
        ValueError: В тексте встретился формат, отличный от заданного.
    """
    if eol_mode != "auto":
        foreign = detect_eol_kinds(text) - {eol_mode}
        if foreign:
            raise ValueError(
                f"ожидался формат переводов строк {eol_mode}, "
                f"обнаружено: {', '.join(sorted(foreign))}"
            )
    return _ANY_EOL.split(text)


def normalize_eol(text: str) -> str:
    """Приводит все переводы строк в тексте к ``\\n``.

    Args:
        text: Исходный текст.

    Returns:
        Текст, в котором любые переводы строк заменены на ``\\n``.
    """
    return _ANY_EOL.sub("\n", text)


def read_lines(path: str | Path, eol_mode: str = "auto") -> list[str]:
    """Читает текстовый файл в UTF-8 и разбивает его на строки.

    Файл открывается с ``newline=""``, чтобы Python не преобразовывал переводы
    строк и их формат можно было проверить. BOM в начале файла допускается.

    Args:
        path: Путь к файлу.
        eol_mode: Допустимый формат переводов строк (см. :func:`split_lines`).

    Returns:
        Список строк файла.

    Raises:
        OSError: Файл не удалось открыть.
        ValueError: Файл не в UTF-8 или формат переводов строк не допускается.
    """
    with open(path, encoding="utf-8-sig", newline="") as handle:
        text = handle.read()
    return split_lines(text, eol_mode)


def write_text(path: str | Path, text: str, eol: str = "crlf") -> Path:
    """Записывает текст в файл UTF-8 с заданным форматом переводов строк.

    Перед записью все переводы строк приводятся к ``\\n``, а затем при записи
    Python заменяет каждый ``\\n`` на нужную последовательность (параметр
    ``newline`` функции :func:`open`). Недостающие папки создаются.

    Args:
        path: Путь к создаваемому файлу.
        text: Записываемый текст.
        eol: Формат переводов строк: ``crlf``, ``lf`` или ``cr``.

    Returns:
        Путь к записанному файлу.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline=EOL_CHARS[eol]) as handle:
        handle.write(normalize_eol(text))
    return target
