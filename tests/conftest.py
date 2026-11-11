"""Общие фикстуры тестов."""

import logging

import pytest

SAMPLE_TASK = """Номер задания: 5-1
Название: Удвоение
Условие: Дано число N.
Выведите 2N.
Ввод: Целое число N.
Вывод: Число 2N.
Решение:
n = int(input())

print(n * 2)
==Тест-кейсы==
=>ТК-1
Ввод:
2
Вывод:
4
=>ТК-2
Ввод:
-3
Вывод:
-6
"""

SAMPLE_TASK_2 = """Номер задания: 5-2
Название: Сумма двух
Условие: Даны два числа.
Ввод: Два числа в отдельных строках.
Вывод: Их сумма.
Решение:
print(int(input()) + int(input()))
==Тест-кейсы==
=>ТК-1
Ввод:
1
2
Вывод:
3
"""


@pytest.fixture
def log():
    """Логгер, сообщения которого перехватывает caplog."""
    logger = logging.getLogger("tc_tools.tests")
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def solution_dir(tmp_path):
    """Папка с одним корректным файлом решений (2 задания, переводы строк CRLF)."""
    folder = tmp_path / "solutions"
    folder.mkdir()
    text = SAMPLE_TASK + "\n\n" + SAMPLE_TASK_2
    (folder / "М24-512_ТестовТТ__5_1_2.txt").write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    return folder
