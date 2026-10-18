"""Write the api's OpenAPI schema to frontend/openapi.json.

The frontend generates its TypeScript types from that file. Run it through
`npm run gen:api` in frontend after changing any response model.
"""

import json
from pathlib import Path

from app.main import app

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def main() -> None:
    """Write the schema as indented JSON with LF line endings."""
    schema = json.dumps(app.openapi(), indent=2) + "\n"
    SCHEMA_PATH.write_text(schema, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
