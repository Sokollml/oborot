"""Экспорт схемы API в docs/openapi.json (из неё фронт генерирует типы: npm run gen:api).

Запуск: cd backend && uv run python -m app.export_openapi
"""

import json
from pathlib import Path

from app.main import app

target = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"OpenAPI сохранён в {target}")
