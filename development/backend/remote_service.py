import winrm

from backend.config import (
    WINRM_HOST,
    WINRM_PORT,
    WINRM_USERNAME,
    WINRM_PASSWORD,
    WINRM_TRANSPORT,
    is_winrm_configured
)


def create_session():
    if not is_winrm_configured():
        raise ValueError("WinRM 접속 정보가 설정되지 않았습니다.")

    return winrm.Session(
        f"http://{WINRM_HOST}:{WINRM_PORT}/wsman",
        auth=(WINRM_USERNAME, WINRM_PASSWORD),
        transport=WINRM_TRANSPORT,
        message_encryption="always",
        operation_timeout_sec=60,
        read_timeout_sec=70
    )


def run_remote_command(command, args=None):
    session = create_session()

    result = session.run_cmd(
        command,
        args or []
    )

    return {
        "status_code": result.status_code,
        "stdout": result.std_out.decode(
            "utf-8", errors="replace"
        ).strip(),
        "stderr": result.std_err.decode(
            "utf-8", errors="replace"
        ).strip()
    }


def check_connection():
    result = run_remote_command("hostname")

    return {
        "connected": result["status_code"] == 0,
        "hostname": result["stdout"],
        "error": result["stderr"]
    }

PACKAGE_CONFIG = {
    "python": {
        "package_id": "Python.Python.3.11",
        "command": "python",
        "args": ["--version"],
        "version_pattern": r"Python\s+(\d+\.\d+\.\d+)"
    },
    "java": {
        "package_id": "EclipseAdoptium.Temurin.21.JDK",
        "command": "java",
        "args": ["-version"],
        "version_pattern": r'version\s+"(21[\d.]*)"'
    },
    "git": {
        "package_id": "Git.Git",
        "command": "git",
        "args": ["--version"],
        "version_pattern": r"git version\s+([\w.]+)"
    }
}

import re


def verify_program(profile):
    if profile not in PACKAGE_CONFIG:
        raise ValueError("지원하지 않는 프로그램입니다.")

    package = PACKAGE_CONFIG[profile]

    result = run_remote_command(
        package["command"],
        package["args"]
    )

    output = result["stdout"] + "\n" + result["stderr"]

    match = re.search(
        package["version_pattern"],
        output
    )

    verified = (
        result["status_code"] == 0
        and match is not None
    )

    return {
        "profile": profile,
        "installed": verified,
        "version": match.group(1) if verified else None,
        "verification": "verified" if verified else "not_verified",
        "log": output.strip()
    }
def install_program(profile):
    if profile not in PACKAGE_CONFIG:
        raise ValueError("지원하지 않는 프로그램입니다.")

    package = PACKAGE_CONFIG[profile]

    # 1. 기존 설치 여부 확인
    before = verify_program(profile)

    # 2. 이미 설치된 경우 설치 생략
    if before["installed"]:
        return {
            "profile": profile,
            "status": "already_installed",
            "installed_version": before["version"],
            "verification": "verified",
            "log": (
                "[SKIP] 이미 설치된 프로그램입니다.\n"
                + before["log"]
            )
        }

    # 3. 실제 원격 설치
    result = run_remote_command(
        "winget",
        [
            "install",
            "--id", package["package_id"],
            "--exact",
            "--source", "winget",
            "--scope", "machine",
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
            "--disable-interactivity"
        ]
    )

    install_log = (
        result["stdout"] + "\n" + result["stderr"]
    ).strip()

    # 4. 설치 명령 실패 처리
    if result["status_code"] != 0:
        return {
            "profile": profile,
            "status": "failed",
            "installed_version": None,
            "verification": "not_verified",
            "log": install_log
        }

    # 5. 설치 후 실행 및 버전 검증
    after = verify_program(profile)

    return {
        "profile": profile,
        "status": (
            "success" if after["installed"]
            else "failed"
        ),
        "installed_version": after["version"],
        "verification": after["verification"],
        "log": install_log + "\n" + after["log"]
    }