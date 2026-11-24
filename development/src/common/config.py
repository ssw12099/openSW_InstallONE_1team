"""프로토타입 전체에서 쓰는 설정값.

값은 환경 변수나 development/.env 파일에서 읽습니다.
API 키·비밀번호는 .env에만 넣고 Git에 올리지 않습니다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:  # python-dotenv가 없어도 환경 변수만으로 동작
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

# development/ 폴더 기준 경로
BASE_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = BASE_DIR / "src"
PROFILES_DIR = BASE_DIR / "profiles"
DB_SCHEMA_FILE = BASE_DIR / "db" / "schema.sql"
UI_DIR = SRC_DIR / "ui"
PLAYBOOK_DIR = SRC_DIR / "installer" / "playbooks"
SEAT_CHECK_SCRIPT = SRC_DIR / "verification" / "seat_check.py"
DEFAULT_SEATS_FILE = SRC_DIR / "common" / "seats.yml"

if load_dotenv is not None:
    load_dotenv(BASE_DIR / ".env")

# AI 공급자별 기본값. 모두 OpenAI 호환 /chat/completions 방식으로 부릅니다.
LLM_PRESETS: dict[str, dict[str, str]] = {
    # HaiGPT는 학교 API 안내에 나온 주소·모델 이름을 .env에 적어서 씁니다.
    "haigpt": {"base_url": "", "model": ""},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-120b"},
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "qwen2.5:7b"},
}


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Settings:
    runtime_dir: Path
    db_path: Path
    seats_file: Path
    llm_provider: str  # none / haigpt / groq / ollama
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout: float
    mock_speed: float  # 모의 좌석 지연 배율 (0이면 즉시 끝남)
    winrm_user: str
    winrm_password_set: bool  # 비밀번호 값은 들고 다니지 않고 설정 여부만 봅니다
    ansible_forks: int

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider not in ("", "none") and bool(self.llm_base_url and self.llm_model)


def _load() -> Settings:
    runtime_dir = Path(_env("INSTALLONE_RUNTIME_DIR") or BASE_DIR / "runtime")
    provider = _env("LLM_PROVIDER", "none").lower() or "none"
    preset = LLM_PRESETS.get(provider, {})
    return Settings(
        runtime_dir=runtime_dir,
        db_path=Path(_env("INSTALLONE_DB") or runtime_dir / "installone.db"),
        seats_file=Path(_env("INSTALLONE_SEATS") or DEFAULT_SEATS_FILE),
        llm_provider=provider,
        llm_base_url=_env("LLM_BASE_URL") or preset.get("base_url", ""),
        llm_api_key=_env("LLM_API_KEY"),
        llm_model=_env("LLM_MODEL") or preset.get("model", ""),
        llm_timeout=float(_env("LLM_TIMEOUT", "20") or 20),
        mock_speed=float(_env("INSTALLONE_MOCK_SPEED", "1") or 1),
        winrm_user=_env("INSTALLONE_WINRM_USER"),
        winrm_password_set=bool(_env("INSTALLONE_WINRM_PASSWORD")),
        ansible_forks=int(_env("INSTALLONE_ANSIBLE_FORKS", "10") or 10),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return _load()


def reload_settings() -> Settings:
    """환경 변수를 바꾼 뒤(테스트 등) 설정을 다시 읽습니다."""
    get_settings.cache_clear()
    return get_settings()
