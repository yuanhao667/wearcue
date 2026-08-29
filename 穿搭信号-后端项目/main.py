import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")
sys.path.insert(0, str(PROJECT_DIR / "backend"))

from app.main import app  # noqa: E402


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", os.getenv("APP_PORT", "8000"))),
    )
