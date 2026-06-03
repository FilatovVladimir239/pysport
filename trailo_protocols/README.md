# TrailO Protocols (Excel & Word)

Экспорт протоколов TrailO в **Excel** и **Word (.docx)**: плагин SportOrg и отдельное окно для файлов `.json` / `.json.gz`.

HTML-протоколы по-прежнему через меню «Отчёты» в SportOrg.

## Плагин SportOrg (рекомендуется при работе в открытой базе)

1. Установите пакет (из корня `pysport`):

```bash
cd trailo_protocols
uv sync
```

2. В SportOrg: **Настройки → Плагины → Добавить**

| Поле | Значение |
|------|----------|
| Executable | путь к `python.exe` из venv (`trailo_protocols\.venv\Scripts\python.exe`) |
| Arguments | `-m trailo_protocols.plugin_main` |
| Enabled | ✓ |

3. Перезапустите SportOrg или перезагрузите плагины. В меню появится группа **TrailO**:
   - *TrailO protocol Excel (with answers)*
   - *TrailO protocol Excel (no answers)*
   - *TrailO protocol Word (.docx)*
   - *Open TrailO output folder*

Файлы сохраняются в папку из настройки плагина `output_dir`. Если она пустая — в  
`Документы/TrailOProtocols` (Windows) или `~/Documents/TrailOProtocols`.

Настройки плагина (JSON в конфиге SportOrg, ключ `sportorg.trailo.excel_protocol`):

```json
{
  "output_dir": "D:\\Reports\\TrailO",
  "open_after_save": true,
  "use_custom_script": false,
  "custom_script": "",
  "docx_template": "",
  "docx_use_fixed_template": true,
  "chief_referee_signature_path": "D:\\Reports\\TrailO\\signatures\\chief.png",
  "secretary_signature_path": "D:\\Reports\\TrailO\\signatures\\secretary.png",
  "federation_stamp_path": "D:\\Reports\\TrailO\\signatures\\federation_stamp.png",
  "evsk_assignments_enabled": true,
  "evsk_competition_status": "championship_russia",
  "evsk_competition_status_text": ""
}
```

| Поле | Назначение |
|------|------------|
| `output_dir` | Папка для `.xlsx` и `.docx` (пусто — `Documents/TrailOProtocols`) |
| `open_after_save` | Открыть файл после сохранения (Windows) |
| `use_custom_script` / `custom_script` | Свой Python-скрипт для Excel вместо встроенного |
| `docx_template` | Путь к шаблону Word (пусто — шаблон из SportOrg, см. ниже) |
| `docx_use_fixed_template` | `true` — сначала `_9_trailo_preo_protocol_fixed.docx`, иначе `9_trailo_preo_protocol.docx` |
| `chief_referee_signature_path` / `secretary_signature_path` | PNG/JPEG сканы подписей для Excel-протокола |
| `federation_stamp_path` | PNG/JPEG печати федерации (справа от ФИО судьи и секретаря) |
| `evsk_assignments_enabled` | Блок «Присвоение званий и разрядов» после таблицы (ЕВСК ОДА, с 26.06.2023) |
| `evsk_competition_status` | Уровень соревнований для МС/КМС по местам: `championship_russia`, `cup_russia`, `first_russia`, `world_youth`, … |
| `evsk_competition_status_text` | Свой текст статуса (если задан — вместо `evsk_competition_status`) |

После таблицы результатов Excel добавляет блок по ЕВСК: **МС/КМС по местам** (PreO/Tempo — личные; эстафета — командные) и **разряды I–III по результату** (КУС и нормы из листа «нормы» для точного ориентирования и спринта). Нужно не менее 8 финишировавших в группе (4 команд в эстафете).

ФИО главного судьи и секретаря по-прежнему в **Свойства события** SportOrg (`chief_referee`, `secretary`). Сканы подписей задаются только в настройках плагина. При первом запуске плагин копирует пути из старых полей заезда, если они ещё были в файле базы.

Word-экспорт использует те же данные, что и **Отчёты → Word** в SportOrg (`format_race_dict_for_trailo_docx`: время PreO в секундах, счётчики КП на дистанции).

Плагин получает снимок **текущего заезда** и обновления по `sportorg.*.update`. Перед экспортом пересчитайте результаты в SportOrg.

## Отдельное приложение (файл базы с диска)

```bash
cd trailo_protocols
uv sync --extra gui
uv run trailo-protocols
```

Или `TrailoProtocols.pyw` (нужен PySide6).

- Открыть файл события SportOrg
- Выбрать заезд
- «Включить ответы», свой скрипт `.py` — как раньше

## Зависимость от SportOrg

`trailo_protocol.py` и расчёт TrailO — в пакете `sportorg`. Запись `.xlsx` — `trailo_protocols/excel.py`, `.docx` — `trailo_protocols/docx.py` (docxtpl).

## Тесты

```bash
cd trailo_protocols
uv run pytest -q
```
