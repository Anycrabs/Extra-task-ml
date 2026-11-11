"""Тесты модуля форматирования: отчёты, справочник тем, имена файлов, XML."""

import xml.etree.ElementTree as ElementTree

import pytest

from tc_tools.converter.__main__ import main
from tc_tools.converter.render import (DEFAULT_TEMPLATE, load_template, output_file_name,
                                       render_questions, validate_output_name)
from tc_tools.converter.reports_reader import collect_report_files, load_statuses, parse_brief_report
from tc_tools.converter.topics import load_topics, topic_title


# ------------------------------------------------------------------ краткие отчёты

def test_parse_brief_report():
    statuses, unknown = parse_brief_report(["3: FAILED", "    3-1: PASSED", "  3-2:FAILED", "мусор", ""])
    assert statuses == {"3-1": "PASSED", "3-2": "FAILED"}
    assert unknown == ["мусор"]


def test_latest_report_wins(tmp_path, log):
    (tmp_path / "Отчет_20260101-100000_all.log").write_text("1: FAILED\n    1-1: FAILED\n    1-2: PASSED\n",
                                                            encoding="utf-8")
    (tmp_path / "Отчет_20260102-100000_all.log").write_text("1: PASSED\n    1-1: PASSED\n", encoding="utf-8")
    (tmp_path / "Отчет_20260103-100000_tc_all.log").write_text("    1-1: FAILED\n", encoding="utf-8")
    assert len(collect_report_files([str(tmp_path)], log)) == 2
    assert load_statuses([str(tmp_path)], "auto", log) == {"1-1": "PASSED", "1-2": "PASSED"}


# ------------------------------------------------------------------ справочник тем

def test_topics_duplicates_and_missing(tmp_path, log, caplog):
    path = tmp_path / "t.csv"
    path.write_text("Номер темы;Название темы\n 1 ;Циклы\n1;Другое\n2;\n", encoding="utf-8")
    topics = load_topics(path, "auto", log)
    assert topics == {"1": "Циклы", "2": ""}
    assert topic_title(topics, "1", log) == "Циклы"
    assert topic_title(topics, "2", log) is None
    assert topic_title(topics, "3", log) is None
    assert topic_title(None, "3", log) is None
    assert "повторяется" in caplog.text and "пустое название" in caplog.text


def test_topics_bad_header_ignored(tmp_path, log, caplog):
    path = tmp_path / "t.csv"
    path.write_text("Номер;Тема\n1;Циклы\n", encoding="utf-8")
    assert load_topics(path, "auto", log) is None
    assert load_topics(tmp_path / "нет.csv", "auto", log) is None
    assert "заголовков" in caplog.text


# ------------------------------------------------------------------ имена и шаблон

def test_output_names():
    topic = {"number": "3", "title": "Ввод/вывод"}
    assert output_file_name("Q_{topic}_{topic_title}_{timestamp}.xml", "T", topic) == "Q_3_Ввод_вывод_T.xml"
    assert output_file_name("Q_{topic_title}.xml", "T", {"number": "4", "title": None}) == "Q_4.xml"
    with pytest.raises(ValueError):
        validate_output_name("Q_{topic}.xml", split_by_topic=False)
    with pytest.raises(ValueError):
        validate_output_name("Q_{unknown}.xml", split_by_topic=True)


def test_template_escapes_and_marks_examples():
    cases = [{"number": i, "input": f"<{i}>", "output": "a & 'b'"} for i in range(1, 6)]
    question = {"id": "1-1", "title": 'Ввод "строки"', "condition": "a < b ]]> c",
                "input_description": "x", "output_description": "y", "solution": "print('<>')",
                "test_cases": cases}
    text = render_questions(load_template(DEFAULT_TEMPLATE),
                            [{"number": "1", "title": None, "questions": [question]}], "T")
    assert text.startswith("<?xml")
    root = ElementTree.fromstring(text.encode("utf-8"))
    coderunner = root.find("question[@type='coderunner']")
    assert coderunner.find("answer").text == "print('<>')"
    tests = coderunner.findall("testcases/testcase")
    assert [tc.get("useasexample") for tc in tests] == ["1", "1", "1", "0", "0"]
    assert tests[4].find("display/text").text == "HIDE"
    assert tests[0].find("stdin/text").text == "<1>"
    assert root.find("question[@type='category']/category/text").text == "$course$/top/Тема 1"


# ------------------------------------------------------------------ сквозной запуск

def test_converter_end_to_end(solution_dir, tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "Отчет_20260101-100000_all.log").write_text("5: FAILED\n    5-1: PASSED\n    5-2: FAILED\n",
                                                           encoding="utf-8")
    out = tmp_path / "xml"
    code = main([str(solution_dir), "--reports", str(reports), "--output-dir", str(out),
                 "--log-dir", str(tmp_path / "logs")])
    assert code == 0
    files = list(out.glob("Questions_all_*.xml"))
    assert len(files) == 1
    root = ElementTree.fromstring(files[0].read_bytes())
    assert [q.find("idnumber").text for q in root.findall("question[@type='coderunner']")] == ["5-1"]


def test_converter_requires_reports_or_ignore(solution_dir, tmp_path):
    assert main([str(solution_dir), "--log-dir", str(tmp_path)]) == 2
    code = main([str(solution_dir), "--ignore-reports", "--split-by-topic",
                 "--output-dir", str(tmp_path / "x"), "--log-dir", str(tmp_path)])
    assert code == 0
    assert len(list((tmp_path / "x").glob("Questions_5_*.xml"))) == 1
