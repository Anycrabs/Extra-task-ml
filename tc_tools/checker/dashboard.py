"""HTML-дашборд по результатам проверки (дополнительная функциональность).

Дашборд — один самодостаточный HTML-файл ``Отчет_<Метка>_dashboard.html``:
без внешних библиотек и интернета, открывается в любом браузере.

Разделение ответственности: этот модуль только считает агрегаты (чистые функции
над списком проверенных файлов), а вся разметка и стили находятся в шаблоне
``templates/dashboard.html.j2``.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..common.constants import PASSED
from .reports import file_sort_key, percent

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
DASHBOARD_TEMPLATE = "dashboard.html.j2"

# Порядок и цвета сегментов кольцевой диаграммы исходов ТК (цвета — CSS-переменные шаблона).
OUTCOMES = (
    ("ok", "Пройдено", "ok"),
    ("mismatch", "Неверный вывод", "warn"),
    ("error", "Ошибка выполнения", "err"),
    ("timeout", "Превышено время", "time"),
)
HISTOGRAM_BINS = ((0, 20, "0–19"), (20, 40, "20–39"), (40, 60, "40–59"),
                  (60, 80, "60–79"), (80, 100, "80–99"), (100, 101, "100"))


def level(value: float) -> str:
    """Уровень результата для раскраски: ``hi`` (≥80 %), ``mid`` (≥50 %), ``lo``.

    Args:
        value: Процент верных.

    Returns:
        Название уровня.
    """
    if value >= 80:
        return "hi"
    return "mid" if value >= 50 else "lo"


def _aggregate(files: list[dict], key) -> list[dict]:
    """Суммирует задания по группам/темам.

    Args:
        files: Проверенные файлы.
        key: Функция, возвращающая подпись группы для файла.

    Returns:
        Список ``{"label", "files", "tasks", "passed", "percent", "level"}``
        в порядке первого появления подписи.
    """
    buckets: dict[str, dict] = {}
    for item in files:
        bucket = buckets.setdefault(key(item), {"label": key(item), "files": 0, "tasks": 0, "passed": 0})
        bucket["files"] += 1
        bucket["tasks"] += len(item["tasks"])
        bucket["passed"] += sum(task["status"] == PASSED for task in item["tasks"])
    for bucket in buckets.values():
        bucket["percent"] = percent(bucket["passed"], bucket["tasks"])
        bucket["level"] = level(bucket["percent"])
    return list(buckets.values())


def _donut(counts: Counter) -> dict:
    """Готовит сегменты кольцевой диаграммы (CSS conic-gradient).

    Args:
        counts: Число ТК по причинам (ok/mismatch/error/timeout).

    Returns:
        ``{"total", "segments": [...], "gradient": str}``.
    """
    total = sum(counts.values())
    segments, stops, start = [], [], 0.0
    for reason, label, color in OUTCOMES:
        count = counts.get(reason, 0)
        share = count / total * 100 if total else 0.0
        segments.append({"label": label, "count": count, "color": color, "share": round(share, 1)})
        if count:
            stops.append(f"var(--{color}) {start:.2f}% {start + share:.2f}%")
            start += share
    gradient = ", ".join(stops) if stops else "var(--track) 0% 100%"
    return {"total": total, "segments": segments, "gradient": gradient}


def _task_hint(task: dict) -> str:
    """Подсказка для квадратика задания в «мозаике»."""
    title = f"{task['id']}"
    if task.get("title"):
        title += f" «{task['title']}»"
    if task.get("format_error"):
        return f"{title}: ошибка оформления"
    results = task["tc_results"]
    if not results:
        return f"{title}: нет тест-кейсов"
    passed = sum(item["status"] == PASSED for item in results)
    return f"{title}: {task['status']}, ТК {passed}/{len(results)}"


def build_dashboard_context(files: list[dict], timestamp: str) -> dict:
    """Считает все показатели для дашборда.

    Args:
        files: Проверенные (и при необходимости отфильтрованные) файлы.
        timestamp: Метка времени запуска.

    Returns:
        Контекст шаблона: ``kpis``, ``donut``, ``histogram``, ``groups``,
        ``topics``, ``rows``, ``issues``, ``group_names``, ``timestamp``.
    """
    ordered = sorted(files, key=file_sort_key)
    tasks = [task for item in ordered for task in item["tasks"]]
    results = [result for task in tasks for result in task["tc_results"]]
    reasons = Counter(result["reason"] for result in results)
    passed_tasks = sum(task["status"] == PASSED for task in tasks)
    students = {(item["group"], item["student"]) for item in ordered if item["student"]}
    anonymous = sum(1 for item in ordered if not item["student"])
    task_percent = percent(passed_tasks, len(tasks))

    rows = []
    for item in ordered:
        total = len(item["tasks"])
        passed = sum(task["status"] == PASSED for task in item["tasks"])
        rows.append({
            "group": item["group"] or "", "student": item["student"] or "",
            "file_no": int(item["file_no"]), "name": item["name"],
            "total": total, "passed": passed, "failed": total - passed,
            "percent": percent(passed, total), "level": level(percent(passed, total)),
            "tasks": [{"id": task["id"], "ok": task["status"] == PASSED, "hint": _task_hint(task)}
                      for task in item["tasks"]],
        })

    histogram = []
    for low, high, label in HISTOGRAM_BINS:
        count = sum(1 for row in rows if low <= row["percent"] < high)
        histogram.append({"label": label, "count": count})
    peak = max((bin_["count"] for bin_ in histogram), default=0)
    for bin_ in histogram:
        bin_["height"] = round(bin_["count"] / peak * 100, 1) if peak else 0

    topics = sorted(_aggregate(ordered, lambda item: item["file_no"]), key=lambda b: int(b["label"]))
    for topic in topics:
        topic["label"] = f"Файл {topic['label']}"

    return {
        "timestamp": timestamp,
        "kpis": [
            {"label": "Студентов", "value": len(students), "note": f"файлов без ФИО: {anonymous}"},
            {"label": "Файлов решений", "value": len(ordered),
             "note": f"полностью верных: {sum(item['status'] == PASSED for item in ordered)}"},
            {"label": "Заданий верно", "value": f"{passed_tasks} / {len(tasks)}",
             "note": f"неверно: {len(tasks) - passed_tasks}"},
            {"label": "% верных заданий", "value": f"{task_percent:.2f}%", "note": "",
             "level": level(task_percent)},
            {"label": "Тест-кейсов пройдено", "value": f"{reasons.get('ok', 0)} / {len(results)}",
             "note": f"{percent(reasons.get('ok', 0), len(results)):.2f}%"},
        ],
        "donut": _donut(reasons),
        "histogram": histogram,
        "groups": _aggregate(ordered, lambda item: item["group"] or "Без группы"),
        "topics": topics,
        "rows": rows,
        "group_names": sorted({row["group"] for row in rows if row["group"]}),
        "issues": {
            "format_errors": sum(1 for task in tasks if task.get("format_error")),
            "no_tests": sum(1 for task in tasks if not task.get("format_error") and not task["tc_results"]),
        },
    }


def render_dashboard(files: list[dict], timestamp: str) -> str:
    """Формирует HTML-код дашборда.

    Args:
        files: Проверенные файлы.
        timestamp: Метка времени запуска.

    Returns:
        HTML-документ в виде строки.
    """
    environment = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True,
                              trim_blocks=True, lstrip_blocks=True)
    template = environment.get_template(DASHBOARD_TEMPLATE)
    return template.render(**build_dashboard_context(files, timestamp))
