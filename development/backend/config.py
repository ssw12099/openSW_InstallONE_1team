import os
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


# AI 설정
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_BASE_URL = os.getenv("AI_BASE_URL", "")
AI_MODEL = os.getenv("AI_MODEL", "")

AI_MODE = os.getenv("AI_MODE", "mock")
INSTALL_MODE = os.getenv("INSTALL_MODE", "mock")


# WinRM 원격 접속 설정
WINRM_HOST = os.getenv("WINRM_HOST", "")
WINRM_PORT = int(os.getenv("WINRM_PORT", "5985"))
WINRM_USERNAME = os.getenv("WINRM_USERNAME", "")
WINRM_PASSWORD = os.getenv("WINRM_PASSWORD", "")
WINRM_TRANSPORT = os.getenv("WINRM_TRANSPORT", "ntlm")


def is_ai_configured():
    return bool(
        AI_API_KEY
        and AI_BASE_URL
        and AI_MODEL
    )


def is_winrm_configured():
    return bool(
        WINRM_HOST
        and WINRM_USERNAME
        and WINRM_PASSWORD
    )

INSTALL_ENGINE = os.getenv("INSTALL_ENGINE", "pywinrm")

ANSIBLE_WSL_DISTRO = os.getenv(
    "ANSIBLE_WSL_DISTRO", "Ubuntu"
)

ANSIBLE_PYTHON_PATH = os.getenv(
    "ANSIBLE_PYTHON_PATH", ""
)


def is_ansible_configured():
    return bool(
        ANSIBLE_WSL_DISTRO
        and ANSIBLE_PYTHON_PATH
        and is_winrm_configured()
    )