"""Тесты модуля проверки: сравнение, запуск решений, отчёты, сквозной запуск."""

import sys

from openpyxl import load_workbook

from tc_tools.checker.__main__ import main
from tc_tools.checker.reports import brief_report, filter_files, summary_rows
from tc_tools.checker.runner import check_task, compare_output

PY = sys.executable


def make_task(solution, cases):
    return {"id": "9-1", "file_no": 9, "number": 1, "title": "t", "solution": solution,
            "test_cases": [{"number": i, "input": inp, "output": out}
                           for i, (inp, out) in enumerate(cases, start=1)]}


# ------------------------------------------------------------------ сравнение

def test_compare_ignores_eol_format_and_final_newline():
    assert compare_output("1\r\n2\r\n", "1\n2")
    assert compare_output("1\r2", "1\n2")
    assert compare_output("\n", "")          # print() при пустом эталоне


def test_compare_is_strict_otherwise():
    assert not compare_output("5 \n", "5")    # пробел
    assert not compare_output("Yes\n", "YES")  # регистр
    assert not compare_output("5.0\n", "5")   # формат числа
    assert not compare_output("a\n\n", "a")   # лишняя пустая строка


# ------------------------------------------------------------------ запуск решений

def test_check_task_statuses():
    result = check_task(make_task("print(int(input()) * 2)", [("2", "4"), ("3", "7")]), 5, PY)
    assert [r["reason"] for r in result["tc_results"]] == ["ok", "mismatch"]
    assert result["status"] == "FAILED"


def test_check_task_runtime_error_has_traceback():
    result = check_task(make_task("print(1 / 0)", [("", "0")]), 5, PY)
    case = result["tc_results"][0]
    assert case["reason"] == "error" and "ZeroDivisionError" in case["error"]


def test_check_task_timeout():
    result = check_task(make_task("while True:\n    pass", [("", "")]), 0.5, PY)
    assert result["tc_results"][0]["reason"] == "timeout"


def test_check_task_utf8_and_crlf_input():
    result = check_task(make_task("print(input()[::-1])", [("мир\r\n", "рим")]), 5, PY)
    assert result["status"] == "PASSED"


def test_task_without_test_cases_failed():
    assert check_task(make_task("print(1)", []), 5, PY)["status"] == "FAILED"


# ------------------------------------------------------------------ отчёты

def _file(group, student, file_no, statuses):
    tasks = [{"id": f"{file_no}-{i}", "status": s, "tc_results": []} for i, s in enumerate(statuses, 1)]
    return {"group": group, "student": student, "file_no": str(file_no), "name": "f.txt",
            "tasks": tasks, "status": "PASSED" if all(s == "PASSED" for s in statuses) else "FAILED"}


def test_summary_sorting_and_percent():
    files = [_file(None, None, 1, ["PASSED"]), _file("М24-512", "Ёлкин", 2, ["PASSED", "FAILED", "FAILED"]),
             _file("М24-512", "Андреев", 3, ["PASSED"]), _file("М24-511", "Яковлев", 4, ["FAILED"])]
    rows = summary_rows(files)
    assert [row["student"] for row in rows] == ["Яковлев", "Андреев", "Ёлкин", None]
    assert rows[2]["percent"] == 33.33


def test_filter_files():
    files = [_file("М24-512", "ИвановИИ", 1, ["PASSED"]), _file("М24-511", "ПетровПП", 2, ["PASSED"])]
    assert len(filter_files(files, ["м24-512"], [], [])) == 1
    assert len(filter_files(files, [], [], ["2"])) == 1
    assert len(filter_files(files, [], [], [])) == 2


def test_brief_report_format():
    text = brief_report([_file(None, None, 3, ["PASSED", "FAILED"])])
    assert text == "3: FAILED\n    3-1: PASSED\n    3-2: FAILED\n"


# ------------------------------------------------------------------ сквозной запуск

def test_checker_end_to_end(solution_dir, tmp_path):
    reports, logs = tmp_path / "reports", tmp_path / "logs"
    code = main([str(solution_dir), "--reports-dir", str(reports), "--log-dir", str(logs),
                 "--output-eol", "lf", "--jobs", "2"])
    assert code == 0
    names = sorted(path.name.split("_", 2)[2] for path in reports.iterdir())
    assert names == ["all.log", "dashboard.html", "results.xlsx", "tc_all.log", "tc_failed.log"]
    brief = next(reports.glob("*_all.log")).read_bytes()
    assert b"\r" not in brief and b"5-1: PASSED" in brief
    sheet = load_workbook(next(reports.glob("*.xlsx")))["Сводка"]
    assert sheet.auto_filter.ref == "A1:G2"
    assert [cell.value for cell in sheet[2]] == ["М24-512", "ТестовТТ", 5, 2, 2, 0, 100]
    assert len(list(logs.glob("Check_log_*.log"))) == 1


def test_checker_reports_can_be_disabled(solution_dir, tmp_path):
    reports = tmp_path / "reports"
    main([str(solution_dir), "--reports-dir", str(reports), "--log-dir", str(tmp_path),
          "--no-xlsx", "--no-dashboard"])
    assert not list(reports.glob("*.xlsx")) and not list(reports.glob("*.html"))
