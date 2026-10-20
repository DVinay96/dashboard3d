import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("PIPELINE_DATA_DIR", tempfile.mkdtemp(prefix="openapi-"))
os.environ.setdefault("PIPELINE_SKIP_DOTENV", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app

out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(create_app().openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("OpenAPI escrito en", out)
