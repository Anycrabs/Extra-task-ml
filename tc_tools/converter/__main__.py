"""Точка входа модуля форматирования заданий.

Примеры::

    python -m tc_tools.converter -c configs/convert.yaml
    python -m tc_tools.converter examples/solutions --reports out/reports --topics examples/topics.csv
    python -m tc_tools.converter examples/solutions --ignore-reports --split-by-topic
"""

from __future__ import annotations

import argparse
import sys

from ..common.config import load_settings
from ..common.textio import INPUT_EOL_MODES, OUTPUT_EOL_MODES
from .pipeline import DEFAULTS, run, validate_settings


def build_arg_parser() -> argparse.ArgumentParser:
    """Создаёт парсер аргументов командной строки.

    Returns:
        Настроенный :class:`argparse.ArgumentParser`.
    """
    toggle = argparse.BooleanOptionalAction
    parser = argparse.ArgumentParser(
        prog="python -m tc_tools.converter",
        description="Формирование вопросов в формате XML по шаблону на основе файлов решений.",
    )
    parser.add_argument("inputs", nargs="*", default=None, help="файлы решений и/или папки с ними")
    parser.add_argument("-c", "--config", help="YAML-файл конфигурации")
    parser.add_argument("--recursive", action=toggle, default=None, help="искать файлы во вложенных папках")
    parser.add_argument("--input-eol", choices=INPUT_EOL_MODES, help="переводы строк во входных файлах")
    parser.add_argument("--output-eol", choices=OUTPUT_EOL_MODES, help="переводы строк в создаваемых файлах")
    parser.add_argument("--reports", action="append",
                        help="краткий отчёт Отчет_<Метка>_all.log или папка с отчётами (можно несколько)")
    parser.add_argument("--ignore-reports", action=toggle, default=None,
                        help="выгрузить все задания без учёта результатов проверки")
    parser.add_argument("--topics", help="справочник тем (CSV)")
    parser.add_argument("--template", help="шаблон Jinja2")
    parser.add_argument("--split-by-topic", action=toggle, default=None, help="отдельный XML-файл на каждую тему")
    parser.add_argument("--output-name", help="шаблон имени: {topic}, {topic_title}, {timestamp}")
    parser.add_argument("--output-dir", help="папка для XML-файлов")
    parser.add_argument("--log-dir", help="папка для логов")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Разбирает аргументы, загружает настройки и запускает форматирование.

    Args:
        argv: Аргументы командной строки (по умолчанию ``sys.argv[1:]``).

    Returns:
        Код завершения: 0 — успешно, 1 — ошибка выполнения, 2 — ошибка настроек.
    """
    arguments = vars(build_arg_parser().parse_args(argv))
    config_path = arguments.pop("config")
    if not arguments["inputs"]:
        arguments["inputs"] = None
    try:
        settings = load_settings(DEFAULTS, config_path, arguments)
        validate_settings(settings)
    except (OSError, ValueError) as exc:
        print(f"Ошибка настроек: {exc}", file=sys.stderr)
        return 2
    return run(settings)


if __name__ == "__main__":
    sys.exit(main())
