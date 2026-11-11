"""Формирование XML по шаблону Jinja2 и имён выходных файлов."""

from __future__ import annotations

import string
import xml.etree.ElementTree as ElementTree
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Template

from ..common.naming import sanitize_filename_part

DEFAULT_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "moodle_coderunner.xml.j2"
DEFAULT_SINGLE_NAME = "Questions_all_{timestamp}.xml"
DEFAULT_SPLIT_NAME = "Questions_{topic}_{timestamp}.xml"
NAME_FIELDS = {"topic", "topic_title", "timestamp"}
TOPIC_FIELDS = {"topic", "topic_title"}


def load_template(path: str | Path) -> Template:
    """Загружает шаблон Jinja2 с автоэкранированием.

    ``autoescape=True`` экранирует спецсимволы ``< > & " '`` во всех
    подставляемых значениях, поэтому XML остаётся корректным при любом тексте
    заданий. ``StrictUndefined`` превращает опечатку в имени переменной шаблона
    в явную ошибку вместо пустой строки.

    Args:
        path: Путь к файлу шаблона.

    Returns:
        Скомпилированный шаблон.

    Raises:
        jinja2.TemplateError: Шаблон не найден или содержит синтаксическую ошибку.
    """
    template_path = Path(path)
    environment = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    return environment.get_template(template_path.name)


def make_question(task: dict) -> dict:
    """Преобразует задание в вопрос для шаблона (набор полей по требованиям).

    Args:
        task: Задание из файла решений.

    Returns:
        Словарь ``id``, ``title``, ``condition``, ``input_description``,
        ``output_description``, ``solution``, ``test_cases``.
    """
    return {
        "id": task["id"],
        "title": task["title"],
        "condition": task["condition"],
        "input_description": task["input_description"],
        "output_description": task["output_description"],
        "solution": task["solution"],
        "test_cases": [{"number": case["number"], "input": case["input"], "output": case["output"]}
                       for case in task["test_cases"]],
    }


def render_questions(template: Template, topics: list[dict], timestamp: str) -> str:
    """Формирует текст XML-файла.

    Args:
        template: Шаблон.
        topics: Темы (``number``, ``title``, ``questions``).
        timestamp: Метка времени (переменная ``generated_at``).

    Returns:
        Текст XML.
    """
    return template.render(generated_at=timestamp, topics=topics)


def xml_problem(text: str) -> str | None:
    """Проверяет, что сформированный текст — корректный (well-formed) XML.

    Args:
        text: Текст XML.

    Returns:
        Описание ошибки или ``None``, если XML корректен.
    """
    try:
        ElementTree.fromstring(text.encode("utf-8"))
    except ElementTree.ParseError as exc:
        return str(exc)
    return None


def validate_output_name(pattern: str, split_by_topic: bool) -> None:
    """Проверяет шаблон имени выходного файла.

    Args:
        pattern: Шаблон имени, например ``Questions_{topic}_{timestamp}.xml``.
        split_by_topic: Включено ли разбиение на файлы по темам.

    Raises:
        ValueError: Неизвестная подстановка или ``{topic}``/``{topic_title}``
            без разбиения по темам.
    """
    try:
        fields = {name for _, name, _, _ in string.Formatter().parse(pattern) if name is not None}
    except ValueError as exc:
        raise ValueError(f"output_name: некорректный шаблон «{pattern}» ({exc})") from exc
    unknown = fields - NAME_FIELDS
    if unknown:
        raise ValueError(f"output_name: неизвестные подстановки {sorted(unknown)}; "
                         f"допустимы {{topic}}, {{topic_title}}, {{timestamp}}")
    if not split_by_topic and fields & TOPIC_FIELDS:
        raise ValueError("output_name: подстановки {topic} и {topic_title} допустимы "
                         "только при разбиении по темам (split_by_topic: true)")


def output_file_name(pattern: str, timestamp: str, topic: dict | None = None) -> str:
    """Формирует имя выходного файла по шаблону.

    Args:
        pattern: Шаблон имени.
        timestamp: Метка времени.
        topic: Тема (при разбиении по темам) или ``None``.

    Returns:
        Имя файла; недопустимые символы в подставленных значениях заменены на ``_``.
    """
    values = {"timestamp": timestamp}
    if topic is not None:
        values["topic"] = sanitize_filename_part(topic["number"])
        values["topic_title"] = sanitize_filename_part(topic["title"] or topic["number"])
    return pattern.format(**values)
