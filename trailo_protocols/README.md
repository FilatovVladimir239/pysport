# TrailO Protocols (Excel)

Отдельное приложение для выгрузки протоколов TrailO в Excel из файла базы SportOrg (`.json` / `.json.gz`).

SportOrg по-прежнему формирует HTML- и Word-протоколы; Excel вынесен сюда.

## Запуск

Из корня репозитория `pysport`:

```bash
cd trailo_protocols
uv sync
uv run trailo-protocols
```

Или двойной щелчок по `TrailoProtocols.pyw` (нужен установленный пакет и PySide6).

## Возможности

- Открыть файл события SportOrg
- Выбрать заезд (если в файле несколько)
- «Включить ответы» — как в отчётах TrailO
- Опционально: свой скрипт `.py` с функцией `export(race, file_name, ...)`

## Зависимость от SportOrg

Логика таблицы протокола (`trailo_protocol.py`) остаётся в пакете `sportorg`; это общая основа для HTML-шаблонов. Запись `.xlsx` — в этом проекте (`trailo_protocols/excel.py`).
