"""Конвейер модуля форматирования: чтение → отбор → группировка по темам → XML.

Модуль не выполняет код решений: решение о включении задания принимается
по кратким отчётам модуля проверки (или все задания включаются, если
задан ``ignore_reports``).
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from pathlib import Path

from jinja2 import TemplateError

from ..common.constants import PASSED
from ..common.discovery import collect_files
from ..common.logsetup import close_logger, say, setup_logger
from ..common.naming import make_timestamp
from ..common.parser import load_solution_file
from ..common.textio import write_text
from .render import (DEFAULT_SINGLE_NAME, DEFAULT_SPLIT_NAME, DEFAULT_TEMPLATE, load_template,
                     make_question, output_file_name, render_questions, validate_output_name,
                     xml_problem)
from .reports_reader import load_statuses
from .topics import load_topics, topic_title

DEFAULTS = {
    "inputs": [],              # файлы решений и/или папки с ними
    "recursive": False,        # искать файлы во вложенных папках
    "input_eol": "auto",       # переводы строк во входных файлах (решения, справочник, отчёты)
    "output_eol": "crlf",      # переводы строк в создаваемых файлах (XML, лог)
    "reports": [],             # краткие отчёты Отчет_<Метка>_all.log и/или папки с ними
    "ignore_reports": False,   # формировать вопросы без учёта результатов проверки
    "topics": None,            # путь к справочнику тем (CSV)
    "template": str(DEFAULT_TEMPLATE),  # путь к шаблону Jinja2
    "split_by_topic": False,   # один XML на тему вместо одного общего
    "output_name": None,       # шаблон имени: {topic}, {topic_title}, {timestamp}
    "output_dir": "xml",       # папка для XML-файлов
    "log_dir": "logs",         # папка для логов
}

EXCLUSION_REASONS = (
    ("failed", "не прошли проверку"),
    ("missing", "отсутствуют в отчёте"),
    ("error", "ошибки обработки"),
)


def validate_settings(settings: dict) -> None:
    """Проверяет настройки и подставляет шаблон имени по умолчанию.

    Args:
        settings: Настройки после :func:`common.config.load_settings`.

    Raises:
        ValueError: Недопустимое значение параметра.
    """
    if not settings["ignore_reports"] and not settings["reports"]:
        raise ValueError("не заданы отчёты проверки (reports); "
                         "для выгрузки без учёта проверки укажите ignore_reports: true")
    if settings["output_name"] is None:
        settings["output_name"] = DEFAULT_SPLIT_NAME if settings["split_by_topic"] else DEFAULT_SINGLE_NAME
    validate_output_name(settings["output_name"], settings["split_by_topic"])


def select_tasks(files: list[dict], statuses: dict[str, str] | None,
                 excluded: Counter, log: logging.Logger) -> list[dict]:
    """Отбирает задания для выгрузки.

    Args:
        files: Разобранные файлы решений.
        statuses: Статусы заданий из отчётов или ``None`` (выгрузка без учёта проверки).
        excluded: Счётчик исключённых заданий по причинам (дополняется).
        log: Логгер.

    Returns:
        Список отобранных заданий.
    """
    selected, seen = [], set()
    for item in files:
        for task in item["tasks"]:
            if task["id"] in seen:
                log.error("%s, задание %s: номер задания повторяется — задание исключено",
                          item["name"], task["id"])
                excluded["error"] += 1
                continue
            seen.add(task["id"])
            if statuses is not None:
                status = statuses.get(task["id"])
                if status is None:
                    log.warning("%s, задание %s: отсутствует в отчётах проверки — исключено",
                                item["name"], task["id"])
                    excluded["missing"] += 1
                    continue
                if status != PASSED:
                    log.warning("%s, задание %s: не прошло проверку (%s) — исключено",
                                item["name"], task["id"], status)
                    excluded["failed"] += 1
                    continue
            selected.append(task)
    return selected


def group_by_topic(tasks: list[dict], topics_reference: dict[str, str] | None,
                   log: logging.Logger) -> list[dict]:
    """Группирует задания по темам (номер темы = номер файла с заданиями).

    Args:
        tasks: Отобранные задания.
        topics_reference: Справочник тем или ``None``.
        log: Логгер.

    Returns:
        Темы по возрастанию номера: ``{"number", "title", "questions"}``,
        вопросы внутри темы — по возрастанию номера задания.
    """
    buckets: dict[str, list[dict]] = defaultdict(list)
    for task in tasks:
        buckets[str(task["file_no"])].append(task)
    topics = []
    for number in sorted(buckets, key=int):
        questions = [make_question(task) for task in sorted(buckets[number], key=lambda t: t["number"])]
        topics.append({"number": number, "title": topic_title(topics_reference, number, log),
                       "questions": questions})
    return topics


def _topic_label(topic: dict) -> str:
    """Подпись темы для статистики."""
    return f"Тема {topic['number']}" + (f" ({topic['title']})" if topic["title"] else "")


def _execute(settings: dict, timestamp: str, log: logging.Logger) -> int:
    """Основная логика запуска (без настройки и закрытия лога)."""
    say(log, f"Модуль форматирования заданий, метка времени {timestamp}")
    try:
        template = load_template(settings["template"])
    except TemplateError as exc:
        log.error("Шаблон %s не загружен: %s", settings["template"], exc)
        return 1

    paths = collect_files(settings["inputs"], recursive=settings["recursive"], log=log)
    if not paths:
        log.error("Не найдено ни одного файла решений")
        return 1

    excluded: Counter = Counter()
    files = []
    for path in paths:
        loaded, dropped = load_solution_file(path, settings["input_eol"], log)
        excluded["error"] += dropped
        if loaded is not None:
            files.append(loaded)

    statuses = None if settings["ignore_reports"] else load_statuses(
        settings["reports"], settings["input_eol"], log)
    reference = load_topics(settings["topics"], settings["input_eol"], log) if settings["topics"] else None
    topics = group_by_topic(select_tasks(files, statuses, excluded, log), reference, log)

    if settings["split_by_topic"]:
        outputs = [(output_file_name(settings["output_name"], timestamp, topic), [topic]) for topic in topics]
    else:
        outputs = [(output_file_name(settings["output_name"], timestamp), topics)] if topics else []
    if not outputs:
        log.warning("Нет заданий для выгрузки — XML-файлы не созданы")

    created = []
    for name, chunk in outputs:
        try:
            text = render_questions(template, chunk, timestamp)
        except TemplateError as exc:
            log.error("%s: ошибка при заполнении шаблона: %s", name, exc)
            continue
        problem = xml_problem(text)
        if problem:
            log.error("%s: сформирован некорректный XML (%s) — проверьте шаблон", name, problem)
        created.append(write_text(Path(settings["output_dir"]) / name, text, settings["output_eol"]))

    _report_stats(log, len(files), len(paths) - len(files), topics, created, excluded)
    return 0


def _report_stats(log: logging.Logger, processed: int, rejected: int, topics: list[dict],
                  created: list[Path], excluded: Counter) -> None:
    """Выводит итоговую статистику в консоль и лог."""
    questions = sum(len(topic["questions"]) for topic in topics)
    say(log, "")
    say(log, "Итоги форматирования:")
    say(log, f"  обработано файлов решений: {processed} (не обработано: {rejected})")
    say(log, f"  тем: {len(topics)}")
    say(log, f"  создано XML-файлов: {len(created)}")
    for path in created:
        say(log, f"    {path}")
    say(log, f"  создано вопросов: {questions}")
    for topic in topics:
        say(log, f"    {_topic_label(topic)}: {len(topic['questions'])}")
    say(log, f"  исключено заданий: {sum(excluded.values())}")
    for key, title in EXCLUSION_REASONS:
        say(log, f"    {title}: {excluded.get(key, 0)}")


def run(settings: dict) -> int:
    """Запускает модуль форматирования с готовыми настройками.

    Args:
        settings: Настройки (см. :data:`DEFAULTS`).

    Returns:
        Код завершения: 0 — успешно, 1 — ошибка.
    """
    timestamp = make_timestamp()
    log, log_path = setup_logger("tc_tools.converter", settings["log_dir"], "Conversion_log",
                                 timestamp, settings["output_eol"])
    try:
        code = _execute(settings, timestamp, log)
    except Exception:  # noqa: BLE001 — любую непредвиденную ошибку фиксируем в логе
        log.exception("Непредвиденная ошибка")
        code = 1
    say(log, f"Лог: {log_path}")
    close_logger(log)
    return code
