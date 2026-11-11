"""Отчёты модуля проверки: краткий, подробные и сводный (xlsx).

Все функции формирования текстовых отчётов — чистые: принимают список
проверенных файлов и возвращают текст. Запись на диск выполняет конвейер
(:mod:`tc_tools.checker.pipeline`) через :func:`common.textio.write_text`.

Проверенный файл — словарь файла решений (см. :func:`common.parser.load_solution_file`),
в котором ``tasks`` заменены результатами проверки и добавлен ``status``.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from ..common.constants import FAILED, PASSED
from .runner import REASON_ERROR, REASON_TIMEOUT

INDENT = "    "
SUMMARY_HEADERS = ("Группа", "Студент", "Номер файла", "Число заданий", "Верно", "Неверно", "% верных")
TASK_HEADERS = ("Группа", "Студент", "Номер файла", "Номер задания", "Название", "Статус",
                "ТК пройдено", "ТК всего", "Комментарий")
REASON_TITLES = {
    "ok": "пройден",
    "mismatch": "неверный вывод",
    "error": "ошибка выполнения",
    "timeout": "превышено время",
}


# ---------------------------------------------------------------- сортировка и отбор

def _alphabetic(text: str) -> str:
    """Ключ алфавитной сортировки: без учёта регистра, «ё» как «е»."""
    return text.casefold().replace("ё", "е")


def file_sort_key(solution_file: dict) -> tuple:
    """Ключ сортировки строк отчётов.

    Порядок: группа (по возрастанию), фамилия (по алфавиту), номер файла.
    Файлы без группы и студента располагаются в конце.

    Args:
        solution_file: Файл решений (нужны ключи ``group``, ``student``, ``file_no``).

    Returns:
        Кортеж для ``sorted``.
    """
    group, student = solution_file["group"], solution_file["student"]
    return (group is None, _alphabetic(group or ""), _alphabetic(student or ""),
            int(solution_file["file_no"]))


def filter_files(files: list[dict], groups: list, students: list, file_numbers: list) -> list[dict]:
    """Отбирает файлы для сводного отчёта и дашборда.

    Пустой фильтр не ограничивает отбор. Группы и студенты сравниваются без
    учёта регистра, номера файлов — как числа.

    Args:
        files: Проверенные файлы.
        groups: Номера групп, например ``["М24-512"]``.
        students: Студенты в виде ``ФамилияИО``.
        file_numbers: Номера файлов с заданиями.

    Returns:
        Отфильтрованный список файлов.
    """
    group_set = {str(item).casefold() for item in groups}
    student_set = {str(item).casefold() for item in students}
    number_set = {int(item) for item in file_numbers}

    def accepted(item: dict) -> bool:
        """Проходит ли файл все заданные фильтры."""
        return ((not group_set or (item["group"] or "").casefold() in group_set)
                and (not student_set or (item["student"] or "").casefold() in student_set)
                and (not number_set or int(item["file_no"]) in number_set))

    return [item for item in files if accepted(item)]


def percent(part: int, whole: int) -> float:
    """Доля в процентах, округлённая до двух знаков; 0 при пустом знаменателе."""
    return round(part / whole * 100, 2) if whole else 0.0


def summary_rows(files: list[dict]) -> list[dict]:
    """Строит строки сводного отчёта: одна строка — один файл решений.

    Args:
        files: Проверенные файлы.

    Returns:
        Список словарей с ключами ``group``, ``student``, ``file_no``, ``total``,
        ``passed``, ``failed``, ``percent``, отсортированный по :func:`file_sort_key`.
    """
    rows = []
    for item in sorted(files, key=file_sort_key):
        total = len(item["tasks"])
        passed = sum(task["status"] == PASSED for task in item["tasks"])
        rows.append({
            "group": item["group"], "student": item["student"], "file_no": int(item["file_no"]),
            "total": total, "passed": passed, "failed": total - passed,
            "percent": percent(passed, total), "name": item["name"],
        })
    return rows


# ---------------------------------------------------------------- текстовые отчёты

def brief_report(files: list[dict]) -> str:
    """Формирует краткий отчёт ``Отчет_<Метка>_all.log``.

    Формат::

        <Номер файла с заданиями>: <PASSED|FAILED>
            <Номер задания>: <PASSED|FAILED>

    Args:
        files: Проверенные файлы.

    Returns:
        Текст отчёта.
    """
    lines = []
    for item in files:
        lines.append(f"{item['file_no']}: {item['status']}")
        lines.extend(f"{INDENT}{task['id']}: {task['status']}" for task in item["tasks"])
    return "\n".join(lines) + "\n"


def _block(title: str, value: str | None, level: int) -> list[str]:
    """Заголовок и многострочное значение с отступами для подробного отчёта."""
    lines = [INDENT * level + title]
    if value:
        lines.extend(INDENT * (level + 1) + line for line in value.split("\n"))
    return lines


def _task_lines(task: dict, only_failed: bool) -> list[str]:
    """Строки подробного отчёта для одного задания."""
    lines = [f"{INDENT}{task['id']}: {task['status']}"]
    if task.get("format_error"):
        lines.append(f"{INDENT * 2}Ошибка оформления: {task['format_error']}")
        return lines
    results = task["tc_results"]
    if not results:
        lines.append(f"{INDENT * 2}Нет тест-кейсов")
        return lines
    if any(item["status"] == FAILED for item in results):
        lines.extend(_block("Решение:", task["solution"], 2))
    for item in results:
        if only_failed and item["status"] == PASSED:
            continue
        lines.append(f"{INDENT * 2}=>ТК-{item['number']}: {item['status']}")
        if item["status"] == PASSED:
            continue
        lines.extend(_block("Ввод:", item["input"], 3))
        lines.extend(_block("Вывод:", item["actual"].rstrip("\r\n"), 3))
        lines.extend(_block("Эталон:", item["expected"], 3))
        if item["reason"] in (REASON_ERROR, REASON_TIMEOUT):
            lines.extend(_block("Ошибка:", item["error"], 3))
    return lines


def detailed_report(files: list[dict], only_failed: bool = False, skip_passed_files: bool = False) -> str:
    """Формирует подробный отчёт (``_tc_all.log`` или ``_tc_failed.log``).

    Решение выводится, если хотя бы один ТК задания не пройден; ``Ввод``,
    ``Вывод``, ``Эталон`` — только для непройденных ТК; ``Ошибка`` — только при
    ошибке выполнения или превышении времени. Для удобства после статуса файла
    в квадратных скобках указано имя файла решений.

    Args:
        files: Проверенные файлы.
        only_failed: Только ошибочные файлы, задания и ТК (отчёт ``_tc_failed.log``).
        skip_passed_files: Не включать файлы без ошибок (для ``_tc_all.log``).

    Returns:
        Текст отчёта.
    """
    sections = []
    for item in files:
        if (only_failed or skip_passed_files) and item["status"] == PASSED:
            continue
        lines = [f"{item['file_no']}: {item['status']}  [{item['name']}]"]
        for task in item["tasks"]:
            if only_failed and task["status"] == PASSED:
                continue
            lines.extend(_task_lines(task, only_failed))
        sections.append("\n".join(lines))
    if not sections:
        return "Ошибок не обнаружено.\n" if only_failed else "Нет данных для отчёта.\n"
    return "\n\n".join(sections) + "\n"


# ---------------------------------------------------------------- сводный отчёт xlsx

def _format_sheet(sheet, widths: list[int]) -> None:
    """Оформляет лист: заголовки, ширина колонок, закрепление и автофильтр."""
    header_fill = PatternFill("solid", fgColor="DDE5F0")
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions


def _task_comment(task: dict) -> str:
    """Короткий комментарий к заданию для листа «Задания»."""
    if task.get("format_error"):
        return f"Ошибка оформления: {task['format_error']}"
    if not task["tc_results"]:
        return "Нет тест-кейсов"
    failed = [f"ТК-{item['number']}: {REASON_TITLES[item['reason']]}"
              for item in task["tc_results"] if item["status"] == FAILED]
    return "; ".join(failed)


def write_results_xlsx(files: list[dict], path: str | Path) -> Path:
    """Создаёт сводный отчёт ``Отчет_<Метка>_results.xlsx``.

    Лист «Сводка» — колонки по требованиям (одна строка — один файл решений),
    лист «Задания» — дополнительно: статус каждого задания. На обоих листах
    установлен автофильтр на строку заголовков.

    Args:
        files: Проверенные (и при необходимости отфильтрованные) файлы.
        path: Путь к создаваемому файлу.

    Returns:
        Путь к созданному файлу.
    """
    workbook = Workbook()
    summary = workbook.active
    summary.title = "Сводка"
    summary.append(SUMMARY_HEADERS)
    for row in summary_rows(files):
        summary.append([row["group"], row["student"], row["file_no"], row["total"],
                        row["passed"], row["failed"], row["percent"]])
    for (cell,) in summary.iter_rows(min_row=2, min_col=7, max_col=7):
        cell.number_format = "0.00"
    _format_sheet(summary, [12, 22, 13, 15, 9, 10, 11])
    if summary.max_row > 1:
        summary.conditional_formatting.add(
            f"G2:G{summary.max_row}",
            ColorScaleRule(start_type="num", start_value=0, start_color="F4B6B6",
                           mid_type="num", mid_value=50, mid_color="FBE3A6",
                           end_type="num", end_value=100, end_color="B7E1C1"),
        )

    tasks_sheet = workbook.create_sheet("Задания")
    tasks_sheet.append(TASK_HEADERS)
    for item in sorted(files, key=file_sort_key):
        for task in item["tasks"]:
            results = task["tc_results"]
            tasks_sheet.append([
                item["group"], item["student"], int(item["file_no"]), task["id"],
                task.get("title"), task["status"],
                sum(result["status"] == PASSED for result in results), len(results),
                _task_comment(task),
            ])
    _format_sheet(tasks_sheet, [12, 22, 13, 15, 32, 10, 12, 10, 60])

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(target)
    return target
