"""
scripts/export_openapi.py: Exporta el esquema OpenAPI de FastAPI a docs/openapi.json.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("python/src").resolve()))
from local_agent.api.app import create_app


def export():
    app = create_app()
    schema = app.openapi()
    out_path = Path("docs/openapi.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
    print(f"[+] Esquema OpenAPI exportado en {out_path.resolve()}")


if __name__ == "__main__":
    export()
