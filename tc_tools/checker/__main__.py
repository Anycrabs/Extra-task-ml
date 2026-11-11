"""Точка входа модуля проверки тест-кейсов.

Примеры::

    python -m tc_tools.checker -c configs/check.yaml
    python -m tc_tools.checker examples/solutions --timeout 2 --no-xlsx
    python -m tc_tools.checker М24-512_ИвановИИ__3_1_3.txt --group М24-512
"""

from __future__ import annotations

import argparse
import sys

from ..common.config import load_settings
from ..common.textio import INPUT_EOL_MODES, OUTPUT_EOL_MODES
from .pipeline import DEFAULTS, run, validate_settings


def build_arg_parser() -> argparse.ArgumentParser:
    """Создаёт парсер аргументов командной строки.

    Аргументы перекрывают значения из YAML-файла; не указанный аргумент
    имеет значение ``None`` и не перекрывает ничего.

    Returns:
        Настроенный :class:`argparse.ArgumentParser`.
    """
    toggle = argparse.BooleanOptionalAction
    parser = argparse.ArgumentParser(
        prog="python -m tc_tools.checker",
        description="Проверка тест-кейсов в файлах решений.",
    )
    parser.add_argument("inputs", nargs="*", default=None, help="файлы решений и/или папки с ними")
    parser.add_argument("-c", "--config", help="YAML-файл конфигурации")
    parser.add_argument("--recursive", action=toggle, default=None, help="искать файлы во вложенных папках")
    parser.add_argument("--input-eol", choices=INPUT_EOL_MODES, help="переводы строк во входных файлах")
    parser.add_argument("--output-eol", choices=OUTPUT_EOL_MODES, help="переводы строк в создаваемых файлах")
    parser.add_argument("--timeout", type=float, help="ограничение времени на один ТК, с (по умолчанию 5)")
    parser.add_argument("--jobs", type=int, help="число параллельно проверяемых заданий")
    parser.add_argument("--python", help="интерпретатор Python для запуска решений")
    parser.add_argument("--reports-dir", help="папка для отчётов")
    parser.add_argument("--log-dir", help="папка для логов")
    parser.add_argument("--xlsx", action=toggle, default=None, help="создавать сводный отчёт xlsx")
    parser.add_argument("--dashboard", action=toggle, default=None, help="создавать HTML-дашборд")
    parser.add_argument("--tc-all-skip-passed", action=toggle, default=None,
                        help="не включать в _tc_all.log файлы без ошибок")
    parser.add_argument("--group", dest="groups", action="append", help="фильтр отчёта: группа (можно несколько)")
    parser.add_argument("--student", dest="students", action="append",
                        help="фильтр отчёта: студент ФамилияИО (можно несколько)")
    parser.add_argument("--file-number", dest="file_numbers", action="append",
                        help="фильтр отчёта: номер файла с заданиями (можно несколько)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Разбирает аргументы, загружает настройки и запускает проверку.

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
