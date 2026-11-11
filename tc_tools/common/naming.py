"""Правила именования: файлы решений, номера заданий, метки времени, отчёты.

Шаблон имени файла решений::

    [<Группа>_<ФамилияИО>__]<Номер файла>_<Номер первого задания>_<Номер последнего>.txt

Пример: ``М24-512_ИвановИИ__3_1_10.txt`` или ``3_1_10.txt``.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime

from .constants import REPORT_PREFIX

# [^\W\d_] — «любая буква» (кириллица или латиница) без цифр и подчёркивания.
SOLUTION_NAME_RE = re.compile(
    r"(?:(?P<group>[^\W\d_]\d{2}-\d{3})_(?P<student>[^\W\d_]+(?:-[^\W\d_]+)*)__)?"
    r"(?P<file_no>\d+)_(?P<first>\d+)_(?P<last>\d+)\.txt",
    re.IGNORECASE,
)
TASK_ID_RE = re.compile(r"(\d+)-(\d+)")
TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"
BRIEF_REPORT_RE = re.compile(rf"{REPORT_PREFIX}_(?P<timestamp>\d{{8}}-\d{{6}})_all\.log")
_FORBIDDEN_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def make_timestamp(moment: datetime | None = None) -> str:
    """Формирует метку времени запуска в формате ``ГГГГММДД-ЧЧММСС``.

    Args:
        moment: Момент времени; по умолчанию — текущее время.

    Returns:
        Строка вида ``20261017-202900``.
    """
    return (moment or datetime.now()).strftime(TIMESTAMP_FORMAT)


def parse_solution_name(file_name: str) -> dict | None:
    """Разбирает имя файла решений.

    Имя предварительно нормализуется в NFC: в macOS кириллические буквы
    «й» и «ё» в именах файлов могут храниться в разложенном виде.

    Args:
        file_name: Имя файла без пути.

    Returns:
        Словарь с ключами ``group``, ``student`` (``None``, если не указаны),
        ``file_no`` (строка без ведущих нулей), ``first``, ``last`` (int)
        или ``None``, если имя не соответствует шаблону.
    """
    match = SOLUTION_NAME_RE.fullmatch(unicodedata.normalize("NFC", file_name))
    if match is None:
        return None
    return {
        "group": match["group"],
        "student": match["student"],
        "file_no": str(int(match["file_no"])),
        "first": int(match["first"]),
        "last": int(match["last"]),
    }


def parse_task_id(text: str) -> tuple[int, int] | None:
    """Разбирает номер задания вида ``3-5``.

    Args:
        text: Строка с номером задания (пробелы по краям допускаются).

    Returns:
        Пара (номер файла с заданиями, номер задания в файле) или ``None``.
    """
    match = TASK_ID_RE.fullmatch(text.strip())
    if match is None:
        return None
    return int(match[1]), int(match[2])


def format_task_id(file_no: int | str, number: int) -> str:
    """Собирает номер задания в каноническом виде ``<файл>-<задание>``.

    Args:
        file_no: Номер файла с заданиями.
        number: Номер задания в файле.

    Returns:
        Строка вида ``3-5``.
    """
    return f"{int(file_no)}-{int(number)}"


def report_name(timestamp: str, suffix: str) -> str:
    """Формирует имя отчёта модуля проверки.

    Args:
        timestamp: Метка времени запуска.
        suffix: Суффикс с расширением, например ``all.log`` или ``results.xlsx``.

    Returns:
        Имя вида ``Отчет_20261017-202900_all.log``.
    """
    return f"{REPORT_PREFIX}_{timestamp}_{suffix}"


def sanitize_filename_part(value: str) -> str:
    """Заменяет символы, недопустимые в именах файлов, на ``_``.

    Args:
        value: Подставляемое в имя файла значение.

    Returns:
        Значение, в котором символы ``\\ / : * ? " < > |`` заменены на ``_``.
    """
    return _FORBIDDEN_FILENAME_CHARS.sub("_", value)
