"""Загрузка настроек: значения по умолчанию ← YAML-файл ← аргументы командной строки.

Каждый модуль задаёт словарь значений по умолчанию. Значения из YAML-файла
перекрывают их, аргументы командной строки (если указаны) перекрывают YAML.
"""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

from .textio import INPUT_EOL_MODES, OUTPUT_EOL_MODES


def load_yaml(path: str | Path) -> dict:
    """Читает YAML-файл конфигурации.

    Args:
        path: Путь к YAML-файлу.

    Returns:
        Словарь настроек (пустой для пустого файла).

    Raises:
        OSError: Файл не удалось открыть.
        ValueError: Файл не является корректным YAML-словарём.
    """
    with open(path, encoding="utf-8") as handle:
        try:
            data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ValueError(f"некорректный YAML в {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: верхний уровень YAML должен быть словарём")
    return data


def as_list(value) -> list:
    """Приводит значение параметра-списка к списку.

    Args:
        value: ``None``, одиночное значение или список.

    Returns:
        Список значений (``None`` → пустой список, скаляр → список из одного элемента).
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def load_settings(defaults: dict, config_path: str | None, overrides: dict) -> dict:
    """Собирает итоговые настройки модуля.

    Args:
        defaults: Значения по умолчанию; их ключи — полный перечень параметров.
        config_path: Путь к YAML-файлу или ``None``.
        overrides: Значения из командной строки; ``None`` означает «не задано».

    Returns:
        Словарь настроек.

    Raises:
        OSError: Не удалось прочитать файл конфигурации.
        ValueError: Неизвестные параметры или недопустимые значения.
    """
    from_file = load_yaml(config_path) if config_path else {}
    unknown = sorted(set(from_file) - set(defaults))
    if unknown:
        raise ValueError(f"неизвестные параметры конфигурации: {', '.join(unknown)}")

    settings = copy.deepcopy(defaults)
    settings.update(from_file)
    settings.update({key: value for key, value in overrides.items() if value is not None})

    for key, default in defaults.items():
        if isinstance(default, list):
            settings[key] = as_list(settings[key])

    if settings.get("input_eol") not in INPUT_EOL_MODES:
        raise ValueError(f"input_eol должен быть одним из: {', '.join(INPUT_EOL_MODES)}")
    if settings.get("output_eol") not in OUTPUT_EOL_MODES:
        raise ValueError(f"output_eol должен быть одним из: {', '.join(OUTPUT_EOL_MODES)}")
    if not settings["inputs"]:
        raise ValueError("не заданы входные файлы решений (inputs)")
    return settings
