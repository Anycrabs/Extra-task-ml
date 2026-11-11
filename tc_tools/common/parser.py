"""Разбор файлов решений.

Алгоритм:

1. Имя файла разбирается по шаблону (:func:`naming.parse_solution_name`).
2. Строки файла делятся на блоки заданий: разделитель — две и более пустые
   строки подряд (:func:`split_blocks`).
3. Каждый блок разбирается последовательно (:func:`parse_task_block`):
   поля ``Номер задания``, ``Название``, ``Условие``, ``Ввод``, ``Вывод``,
   ``Решение`` идут в фиксированном порядке; поле продолжается до строки,
   начинающейся со следующего ключевого слова. После строки ``==Тест-кейсы==``
   идут тест-кейсы (:func:`parse_test_cases`).
4. Проверяется, что номера заданий совпадают с диапазоном из имени файла
   (:func:`load_solution_file`).

Разобранные данные представлены обычными словарями (ключи описаны в docstring
функций), переводы строк внутри значений — всегда ``\\n``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable

from .naming import format_task_id, parse_solution_name, parse_task_id
from .textio import read_lines

TASK_KEY = "Номер задания:"
HEADER_FIELDS = (
    ("title", "Название:"),
    ("condition", "Условие:"),
    ("input_description", "Ввод:"),
    ("output_description", "Вывод:"),
    ("solution", "Решение:"),
)
REQUIRED_FIELDS = {"title": "Название:", "solution": "Решение:"}
TC_SECTION = "==Тест-кейсы=="
# Допускаем как кириллические, так и латинские буквы «ТК»/«TK» — частая опечатка.
TC_HEADER_RE = re.compile(r"=>[ТT][КK]-(\d+)")
TC_INPUT_KEY = "Ввод:"
TC_OUTPUT_KEY = "Вывод:"


def is_blank(line: str) -> bool:
    """Проверяет, является ли строка пустой (допускаются пробельные символы).

    Args:
        line: Строка файла.

    Returns:
        ``True``, если строка пустая или состоит только из пробельных символов.
    """
    return not line.strip()


def strip_blank_edges(lines: list[str], leading: bool = True) -> list[str]:
    """Удаляет пустые строки в конце (и, при необходимости, в начале) списка.

    Args:
        lines: Список строк.
        leading: Удалять ли пустые строки в начале.

    Returns:
        Новый список строк без пустых строк по краям.
    """
    start, end = 0, len(lines)
    if leading:
        while start < end and is_blank(lines[start]):
            start += 1
    while end > start and is_blank(lines[end - 1]):
        end -= 1
    return list(lines[start:end])


def split_blocks(lines: list[str]) -> list[tuple[int, list[str]]]:
    """Делит строки файла на блоки заданий.

    Разделитель — две и более пустые строки подряд. Одиночные пустые строки
    остаются внутри блока.

    Args:
        lines: Строки файла решений.

    Returns:
        Список пар (номер первой строки блока в файле, начиная с 1; строки блока).
    """
    blocks: list[tuple[int, list[str]]] = []
    current: list[str] = []
    start_line = 0
    blank_run = 0
    for line_no, line in enumerate(lines, start=1):
        if is_blank(line):
            blank_run += 1
            if current:
                current.append(line)
            continue
        if current and blank_run >= 2:
            blocks.append((start_line, strip_blank_edges(current)))
            current = []
        if not current:
            start_line = line_no
        current.append(line)
        blank_run = 0
    if current:
        blocks.append((start_line, strip_blank_edges(current)))
    return blocks


def _take_until(lines: list[str], pos: int, stop: Callable[[str], bool]) -> tuple[list[str], int]:
    """Собирает строки, начиная с ``pos``, до первой строки, удовлетворяющей ``stop``.

    Args:
        lines: Строки блока.
        pos: Индекс первой собираемой строки.
        stop: Условие остановки.

    Returns:
        Пара (собранные строки, индекс строки-остановки или ``len(lines)``).
    """
    taken = []
    while pos < len(lines) and not stop(lines[pos]):
        taken.append(lines[pos])
        pos += 1
    return taken, pos


def _rest_after_key(line: str, key: str) -> list[str]:
    """Возвращает текст после ключевого слова как список из 0 или 1 строки.

    Args:
        line: Строка, начинающаяся с ключевого слова.
        key: Ключевое слово с двоеточием.

    Returns:
        ``[текст]``, если после ключевого слова что-то есть, иначе ``[]``.
    """
    rest = line[len(key):].strip()
    return [rest] if rest else []


def _is_tc_header(line: str) -> bool:
    """Проверяет, является ли строка заголовком тест-кейса ``=>ТК-N``."""
    return TC_HEADER_RE.fullmatch(line.strip()) is not None


def parse_test_cases(lines: list[str], first_line_no: int = 1) -> list[dict]:
    """Разбирает раздел тест-кейсов (строки после ``==Тест-кейсы==``).

    Значения ``Ввод``/``Вывод`` сохраняются построчно без изменений; удаляются
    только пустые строки в конце значения (они относятся к оформлению файла).

    Args:
        lines: Строки раздела тест-кейсов.
        first_line_no: Номер первой строки раздела в файле (для сообщений об ошибках).

    Returns:
        Список словарей ``{"number": int, "input": str, "output": str}``.

    Raises:
        ValueError: Нарушен формат или нумерация тест-кейсов.
    """
    cases: list[dict] = []
    pos = 0
    while pos < len(lines):
        line = lines[pos]
        if is_blank(line):
            pos += 1
            continue
        expected = len(cases) + 1
        header = TC_HEADER_RE.fullmatch(line.strip())
        if header is None:
            raise ValueError(
                f"строка {first_line_no + pos}: ожидался заголовок «=>ТК-{expected}», "
                f"найдено «{line.strip()}»"
            )
        number = int(header[1])
        if number != expected:
            raise ValueError(
                f"строка {first_line_no + pos}: нарушена нумерация тест-кейсов "
                f"(ТК-{number} вместо ТК-{expected})"
            )
        pos += 1
        if pos >= len(lines) or not lines[pos].startswith(TC_INPUT_KEY):
            raise ValueError(f"ТК-{number}: после заголовка ожидалась строка «{TC_INPUT_KEY}»")
        input_lines = _rest_after_key(lines[pos], TC_INPUT_KEY)
        body, pos = _take_until(lines, pos + 1, lambda text: text.startswith(TC_OUTPUT_KEY))
        input_lines += body
        if pos >= len(lines):
            raise ValueError(f"ТК-{number}: отсутствует строка «{TC_OUTPUT_KEY}»")
        output_lines = _rest_after_key(lines[pos], TC_OUTPUT_KEY)
        body, pos = _take_until(lines, pos + 1, _is_tc_header)
        output_lines += body
        cases.append({
            "number": number,
            "input": "\n".join(strip_blank_edges(input_lines, leading=False)),
            "output": "\n".join(strip_blank_edges(output_lines, leading=False)),
        })
    return cases


def parse_task_block(lines: list[str], first_line_no: int = 1) -> dict:
    """Разбирает один блок задания.

    Args:
        lines: Строки блока (без пустых строк по краям).
        first_line_no: Номер первой строки блока в файле (для сообщений об ошибках).

    Returns:
        Словарь задания с ключами ``id`` (``"3-5"``), ``file_no`` (int),
        ``number`` (int), ``title``, ``condition``, ``input_description``,
        ``output_description``, ``solution`` (str) и ``test_cases`` (list).

    Raises:
        ValueError: Блок оформлен некорректно.
    """
    if not lines or not lines[0].startswith(TASK_KEY):
        raise ValueError(f"блок не начинается со строки «{TASK_KEY}»")
    raw_id = lines[0][len(TASK_KEY):].strip()
    parsed_id = parse_task_id(raw_id)
    if parsed_id is None:
        raise ValueError(f"некорректный номер задания «{raw_id}»")
    file_no, number = parsed_id
    task: dict = {"id": format_task_id(file_no, number), "file_no": file_no, "number": number}

    pos = 1
    for index, (field, key) in enumerate(HEADER_FIELDS):
        if pos >= len(lines) or not lines[pos].startswith(key):
            raise ValueError(f"строка {first_line_no + pos}: ожидалось поле «{key}»")
        head = _rest_after_key(lines[pos], key)
        if index + 1 < len(HEADER_FIELDS):
            next_key = HEADER_FIELDS[index + 1][1]
            body, pos = _take_until(lines, pos + 1, lambda text, k=next_key: text.startswith(k))
        else:
            body, pos = _take_until(lines, pos + 1, lambda text: text.strip() == TC_SECTION)
        if field == "solution":
            # В коде важны отступы, поэтому строки не обрезаются.
            task[field] = "\n".join(strip_blank_edges(head + body))
        else:
            task[field] = "\n".join(head + body).strip()

    for field, key in REQUIRED_FIELDS.items():
        if not task[field]:
            raise ValueError(f"пустое поле «{key}»")
    if pos >= len(lines):
        raise ValueError(f"отсутствует раздел «{TC_SECTION}»")
    task["test_cases"] = parse_test_cases(lines[pos + 1:], first_line_no + pos + 1)
    return task


def _peek_task_id(block: list[str]) -> tuple[int, int] | None:
    """Пытается определить номер задания по первой строке блока.

    Используется, когда блок не удалось разобрать целиком, чтобы указать номер
    задания в сообщении об ошибке и учесть его при проверке диапазона.
    """
    if block and block[0].startswith(TASK_KEY):
        return parse_task_id(block[0][len(TASK_KEY):])
    return None


def _format_numbers(numbers: list[int]) -> str:
    """Форматирует список номеров для сообщения об ошибке."""
    return ", ".join(str(number) for number in numbers) or "нет"


def load_solution_file(
    path: str | Path, eol_mode: str, log: logging.Logger
) -> tuple[dict | None, int]:
    """Читает и разбирает файл решений, записывая все ошибки в лог.

    Некорректно оформленное задание пропускается (попадает в список ``broken``),
    остальные задания файла обрабатываются. Файл целиком не обрабатывается, если:
    имя не соответствует шаблону; файл не читается (кодировка, формат переводов
    строк); номера заданий не совпадают с диапазоном из имени или номер файла
    в поле «Номер задания» не совпадает с указанным в имени.

    Args:
        path: Путь к файлу решений.
        eol_mode: Допустимый формат переводов строк во входных файлах.
        log: Логгер модуля.

    Returns:
        Пара (файл, число заданий, исключённых из-за ошибок). Файл — словарь
        с ключами ``path``, ``name``, ``group``, ``student``, ``file_no`` (str),
        ``first``, ``last``, ``tasks`` (корректные задания по возрастанию номера)
        и ``broken`` (``[{"id", "file_no", "number", "error"}]``);
        ``None``, если файл не обработан.
    """
    path = Path(path)
    meta = parse_solution_name(path.name)
    if meta is None:
        log.error(
            "%s: имя файла не соответствует шаблону "
            "[<Группа>_<ФамилияИО>__]<Номер файла>_<Первое>_<Последнее>.txt — файл пропущен",
            path.name,
        )
        return None, 0
    try:
        lines = read_lines(path, eol_mode)
    except (OSError, ValueError) as exc:
        log.error("%s: не удалось прочитать файл (%s) — файл пропущен", path.name, exc)
        return None, 0

    blocks = split_blocks(lines)
    if not blocks:
        log.error("%s: файл не содержит заданий — файл пропущен", path.name)
        return None, 0

    tasks: list[dict] = []
    broken: list[dict] = []
    numbers: list[tuple[int, int]] = []
    for start_line, block in blocks:
        try:
            task = parse_task_block(block, start_line)
        except ValueError as exc:
            peeked = _peek_task_id(block)
            label = format_task_id(*peeked) if peeked else "номер не определён"
            log.error("%s, задание %s (строка %d): %s — задание пропущено",
                      path.name, label, start_line, exc)
            if peeked:
                numbers.append(peeked)
                broken.append({"id": label, "file_no": peeked[0], "number": peeked[1],
                               "error": str(exc)})
            continue
        numbers.append((task["file_no"], task["number"]))
        tasks.append(task)

    file_no = int(meta["file_no"])
    wrong_files = sorted({number_file for number_file, _ in numbers if number_file != file_no})
    if wrong_files:
        log.error("%s: номер файла с заданиями в поле «Номер задания» (%s) не совпадает "
                  "с указанным в имени (%s) — файл не обработан",
                  path.name, _format_numbers(wrong_files), file_no)
        return None, len(blocks)
    found = sorted(number for _, number in numbers)
    if found != list(range(meta["first"], meta["last"] + 1)):
        log.error("%s: номера заданий в файле (%s) не совпадают с диапазоном %d–%d "
                  "из имени файла — файл не обработан",
                  path.name, _format_numbers(found), meta["first"], meta["last"])
        return None, len(blocks)

    log.debug("%s: разобрано заданий — %d, с ошибками оформления — %d",
              path.name, len(tasks), len(broken))
    solution_file = {
        "path": path,
        "name": path.name,
        **meta,
        "tasks": sorted(tasks, key=lambda item: item["number"]),
        "broken": sorted(broken, key=lambda item: item["number"]),
    }
    return solution_file, len(broken)
