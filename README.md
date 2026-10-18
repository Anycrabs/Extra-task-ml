# Предварительная архитектура проекта

```
tc_tools/
├── common/
│   ├── config.py        # загрузка YAML + CLI-переопределения, дефолты, валидация
│   ├── eol.py           # определение/проверка/нормализация переводов строк
│   ├── textio.py        # read_lines(path, eol_mode), write_text(path, lines, eol)
│   ├── naming.py        # regex имени файла решений, метка времени, санитизация имён
│   ├── discovery.py     # список файлов из путей/папок (+ glob)
│   ├── parser.py        # файл решений -> список заданий (state machine)
│   ├── validation.py    # проверки диапазона, нумерации ТК, обязательных полей
│   └── logsetup.py      # логгер с нужным EOL и UTF-8
├── checker/
│   ├── __main__.py      # точка входа: python -m tc_tools.checker
│   ├── pipeline.py      # оркестрация: parse -> run -> aggregate -> reports
│   ├── runner.py        # запуск решения на одном ТК
│   ├── compare.py       # построчное сравнение
│   ├── aggregate.py     # статусы ТК -> задание -> файл
│   └── reports/
│       ├── brief.py     # _all.log
│       ├── detailed.py  # _tc_all.log, _tc_failed.log
│       └── xlsx.py      # _results.xlsx (openpyxl)
├── converter/
│   ├── __main__.py      # python -m tc_tools.converter
│   ├── pipeline.py
│   ├── reports_reader.py# парсинг _all.log, выбор по метке времени
│   ├── topics.py        # справочник тем (CSV ;)
│   ├── selection.py     # отбор заданий + причины исключения
│   ├── context.py       # сборка контекста шаблона (topics/questions/test_cases)
│   ├── render.py        # Jinja2 Environment(autoescape=True)
│   ├── output_names.py  # шаблон имени выходного файла
│   └── stats.py         # итоговая статистика
├── templates/moodle_coderunner.xml.j2
├── configs/check.example.yaml, convert.example.yaml
├── tests/ (pytest + fixtures/)
├── requirements.txt     # PyYAML, Jinja2, openpyxl (+ pytest для разработки)
└── README.md
```
