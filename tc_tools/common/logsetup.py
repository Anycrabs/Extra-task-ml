"""Настройка логирования: файл лога в UTF-8 с нужным форматом переводов строк.

В файл пишутся все сообщения (уровень DEBUG и выше), в консоль — только
предупреждения и ошибки. Ход работы и итоговая статистика выводятся в консоль
функцией :func:`say`, которая дублирует сообщение в лог.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from .textio import EOL_CHARS

FILE_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
CONSOLE_FORMAT = "[%(levelname)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
FILE_HANDLER_NAME = "tc_tools_file"


def setup_logger(
    name: str,
    log_dir: str | Path,
    file_prefix: str,
    timestamp: str,
    eol: str = "crlf",
) -> tuple[logging.Logger, Path]:
    """Создаёт логгер, пишущий в файл ``<file_prefix>_<timestamp>.log``.

    Поток файла открывается с ``newline=<EOL>``: при записи Python заменяет
    каждый ``\\n`` (в том числе внутри многострочных сообщений и traceback)
    на заданную последовательность перевода строки.

    Args:
        name: Имя логгера.
        log_dir: Папка для файла лога (создаётся при необходимости).
        file_prefix: Префикс имени файла, например ``Check_log``.
        timestamp: Метка времени запуска.
        eol: Формат переводов строк в файле лога.

    Returns:
        Пара (логгер, путь к файлу лога).
    """
    folder = Path(log_dir)
    folder.mkdir(parents=True, exist_ok=True)
    log_path = folder / f"{file_prefix}_{timestamp}.log"

    logger = logging.getLogger(name)
    close_logger(logger)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    stream = open(log_path, "w", encoding="utf-8", newline=EOL_CHARS[eol])
    file_handler = logging.StreamHandler(stream)
    file_handler.set_name(FILE_HANDLER_NAME)  # по имени закрываем только свой файл
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT, DATE_FORMAT))

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger, log_path


def close_logger(logger: logging.Logger) -> None:
    """Отключает обработчики логгера и закрывает файлы логов.

    Args:
        logger: Логгер, созданный :func:`setup_logger`.
    """
    for handler in list(logger.handlers):
        handler.flush()
        logger.removeHandler(handler)
        if handler.get_name() == FILE_HANDLER_NAME:
            handler.stream.close()


def say(logger: logging.Logger, message: str) -> None:
    """Выводит сообщение в консоль и записывает его в лог с уровнем INFO.

    Args:
        logger: Логгер модуля.
        message: Текст сообщения.
    """
    print(message)
    logger.info(message)
