import os
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_BASE_URL = os.getenv("AI_BASE_URL", "")
AI_MODEL = os.getenv("AI_MODEL", "")

AI_MODE = os.getenv("AI_MODE", "mock")
INSTALL_MODE = os.getenv("INSTALL_MODE", "mock")


def is_ai_configured():
    return bool(
        AI_API_KEY
        and AI_BASE_URL
        and AI_MODEL
    )