"""Тесты общего кода: переводы строк, имена файлов, разбор файлов решений, настройки."""

import pytest

from tc_tools.common.config import load_settings
from tc_tools.common.naming import parse_solution_name, sanitize_filename_part
from tc_tools.common.parser import load_solution_file, parse_task_block, split_blocks
from tc_tools.common.textio import detect_eol_kinds, split_lines, write_text

from .conftest import SAMPLE_TASK, SAMPLE_TASK_2


# ------------------------------------------------------------------ переводы строк

def test_split_lines_auto_accepts_mixed():
    assert split_lines("a\r\nb\nc\rd") == ["a", "b", "c", "d"]


def test_split_lines_strict_rejects_foreign_format():
    with pytest.raises(ValueError):
        split_lines("a\r\nb\nc", "crlf")
    assert split_lines("a\nb\n", "lf") == ["a", "b", ""]


def test_detect_eol_kinds():
    assert detect_eol_kinds("a\r\nb\rc") == {"crlf", "cr"}
    assert detect_eol_kinds("abc") == set()


@pytest.mark.parametrize("eol, raw", [("crlf", b"a\r\nb\r\n"), ("lf", b"a\nb\n"), ("cr", b"a\rb\r")])
def test_write_text_uses_requested_eol(tmp_path, eol, raw):
    path = write_text(tmp_path / "out.txt", "a\r\nb\n", eol)
    assert path.read_bytes() == raw


# ------------------------------------------------------------------ имена файлов

def test_parse_solution_name_full_and_short():
    assert parse_solution_name("М24-512_ИвановИИ__3_1_10.txt") == {
        "group": "М24-512", "student": "ИвановИИ", "file_no": "3", "first": 1, "last": 10}
    short = parse_solution_name("3_1_10.txt")
    assert short["group"] is None and short["student"] is None


@pytest.mark.parametrize("name", [
    "М24-512__3_1_10.txt",          # группа без фамилии
    "ИвановИИ__3_1_10.txt",         # фамилия без группы
    "М24-512_ИвановИИ_3_1_10.txt",  # одно подчёркивание вместо двух
    "М2-512_ИвановИИ__3_1_10.txt",  # неверный формат группы
    "3_1.txt",
])
def test_parse_solution_name_rejects_invalid(name):
    assert parse_solution_name(name) is None


def test_sanitize_filename_part():
    assert sanitize_filename_part('Ввод/вывод: "строки"?') == "Ввод_вывод_ _строки__"


# ------------------------------------------------------------------ разбор заданий

def test_parse_task_block_fields():
    task = parse_task_block(SAMPLE_TASK.split("\n"))
    assert task["id"] == "5-1"
    assert task["condition"] == "Дано число N.\nВыведите 2N."
    assert task["solution"] == "n = int(input())\n\nprint(n * 2)"
    assert [case["output"] for case in task["test_cases"]] == ["4", "-6"]


def test_split_blocks_by_two_blank_lines():
    lines = (SAMPLE_TASK + "\n\n" + SAMPLE_TASK_2).split("\n")
    blocks = split_blocks(lines)
    assert [block[0][:16] for _, block in blocks] == ["Номер задания: 5", "Номер задания: 5"]
    assert blocks[1][0] == SAMPLE_TASK.count("\n") + 3


def test_parse_task_block_rejects_wrong_tc_numbering():
    broken = SAMPLE_TASK.replace("=>ТК-2", "=>ТК-3")
    with pytest.raises(ValueError, match="нумерация"):
        parse_task_block(broken.split("\n"))


def test_parse_task_block_rejects_missing_field():
    with pytest.raises(ValueError, match="Решение"):
        parse_task_block(SAMPLE_TASK.replace("Решение:", "Решения:").split("\n"))


def test_empty_tc_section_gives_no_test_cases():
    text = SAMPLE_TASK.split("=>ТК-1")[0]
    assert parse_task_block(text.split("\n"))["test_cases"] == []


def test_load_solution_file_ok(solution_dir, log):
    loaded, dropped = load_solution_file(next(solution_dir.iterdir()), "crlf", log)
    assert dropped == 0
    assert [task["id"] for task in loaded["tasks"]] == ["5-1", "5-2"]
    assert loaded["group"] == "М24-512"


def test_load_solution_file_rejects_range_mismatch(tmp_path, log, caplog):
    path = tmp_path / "5_1_3.txt"
    path.write_text(SAMPLE_TASK + "\n\n" + SAMPLE_TASK_2, encoding="utf-8")
    loaded, dropped = load_solution_file(path, "auto", log)
    assert loaded is None and dropped == 2
    assert "не совпадают с диапазоном" in caplog.text


def test_load_solution_file_rejects_file_number_mismatch(tmp_path, log, caplog):
    path = tmp_path / "6_1_2.txt"
    path.write_text(SAMPLE_TASK + "\n\n" + SAMPLE_TASK_2, encoding="utf-8")
    assert load_solution_file(path, "auto", log)[0] is None
    assert "номер файла" in caplog.text


def test_load_solution_file_rejects_wrong_eol(solution_dir, log, caplog):
    loaded, _ = load_solution_file(next(solution_dir.iterdir()), "lf", log)
    assert loaded is None
    assert "переводов строк" in caplog.text


def test_broken_task_is_skipped_but_file_processed(tmp_path, log):
    path = tmp_path / "5_1_2.txt"
    path.write_text(SAMPLE_TASK + "\n\n" + SAMPLE_TASK_2.replace("Название:", "Имя:"), encoding="utf-8")
    loaded, dropped = load_solution_file(path, "auto", log)
    assert dropped == 1
    assert [task["id"] for task in loaded["tasks"]] == ["5-1"]
    assert loaded["broken"][0]["id"] == "5-2"


# ------------------------------------------------------------------ настройки

def test_load_settings_priority(tmp_path):
    config = tmp_path / "c.yaml"
    config.write_text("inputs: a\ntimeout: 2\n", encoding="utf-8")
    defaults = {"inputs": [], "timeout": 5, "input_eol": "auto", "output_eol": "crlf"}
    settings = load_settings(defaults, str(config), {"timeout": 7, "inputs": None})
    assert settings == {"inputs": ["a"], "timeout": 7, "input_eol": "auto", "output_eol": "crlf"}


def test_load_settings_rejects_unknown_key_and_auto_output(tmp_path):
    defaults = {"inputs": ["x"], "input_eol": "auto", "output_eol": "crlf"}
    config = tmp_path / "c.yaml"
    config.write_text("typo_key: 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="typo_key"):
        load_settings(defaults, str(config), {})
    with pytest.raises(ValueError, match="output_eol"):
        load_settings(defaults, None, {"output_eol": "auto"})
