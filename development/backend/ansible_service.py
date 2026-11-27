import subprocess
import re

from backend.remote_service import PACKAGE_CONFIG

from backend.config import (
    BASE_DIR,
    ANSIBLE_WSL_DISTRO,
    ANSIBLE_PYTHON_PATH,
    is_ansible_configured
)


SUPPORTED_ACTIONS = {
    "check",
    "python",
    "java",
    "git",
    "verify"
}


def run_ansible(action):
    if action not in SUPPORTED_ACTIONS:
        raise ValueError(f"Unsupported action: {action}")

    if not is_ansible_configured():
        raise RuntimeError(
            "Ansible 실행 설정이 완료되지 않았습니다."
        )

    runner_path = BASE_DIR / "ansible" / "run_playbook.py"

    if not runner_path.is_file():
        raise FileNotFoundError(runner_path)

    try:
        path_result = subprocess.run(
            [
                "wsl.exe",
                "-d", ANSIBLE_WSL_DISTRO,
                "--",
                "wslpath",
                "-a", runner_path.as_posix()
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=True
        )

        linux_path = path_result.stdout.strip()

        result = subprocess.run(
            [
                "wsl.exe",
                "-d", ANSIBLE_WSL_DISTRO,
                "--",
                ANSIBLE_PYTHON_PATH,
                linux_path,
                action
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600
        )

        return {
            "engine": "ansible",
            "action": action,
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }

    except subprocess.TimeoutExpired:
        return {
            "engine": "ansible",
            "action": action,
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": "Ansible 실행 시간 초과"
        }

    except (OSError, subprocess.CalledProcessError) as error:
        return {
            "engine": "ansible",
            "action": action,
            "success": False,
            "return_code": -1,
            "stdout": "",
            "stderr": (
                f"Ansible 실행 실패: {type(error).__name__}"
            )
        }


def install_program_ansible(profile):
    if profile not in PACKAGE_CONFIG:
        raise ValueError("지원하지 않는 프로그램입니다.")

    result = run_ansible(profile)

    output = (
        result["stdout"] + "\n" + result["stderr"]
    ).strip()

    log = "[ANSIBLE]\n" + output

    # 1. Playbook 실행 실패 처리
    if not result["success"]:
        return {
            "profile": profile,
            "status": "failed",
            "installed_version": None,
            "verification": "not_verified",
            "log": log
        }

    # 2. Ansible 출력 문자열 정규화
    normalized_output = (
        output
        .replace('\\"', '"')
        .replace("\\r\\n", "\n")
        .replace("\\n", "\n")
    )

    # 3. 설치 버전 추출
    package = PACKAGE_CONFIG[profile]

    version_match = re.search(
        package["version_pattern"],
        normalized_output
    )

    # 4. Ansible 실행 결과 확인
    recap_match = re.search(
        r"PC-01\s*:\s*ok=(\d+)\s+changed=(\d+)"
        r"\s+unreachable=(\d+)\s+failed=(\d+)"
        r"\s+skipped=(\d+)",
        output
    )

    if not version_match or not recap_match:
        return {
            "profile": profile,
            "status": "failed",
            "installed_version": None,
            "verification": "not_verified",
            "log": log + "\n[ERROR] 설치 결과 확인 실패"
        }

    changed = int(recap_match.group(2))
    unreachable = int(recap_match.group(3))
    failed = int(recap_match.group(4))
    skipped = int(recap_match.group(5))

    # 5. 원격 연결 및 작업 실패 확인
    if unreachable > 0 or failed > 0:
        return {
            "profile": profile,
            "status": "failed",
            "installed_version": None,
            "verification": "not_verified",
            "log": log
        }

    # 6. 신규 설치 또는 기존 설치 구분
    if changed > 0:
        status = "success"

    elif skipped > 0:
        status = "already_installed"

    else:
        return {
            "profile": profile,
            "status": "failed",
            "installed_version": None,
            "verification": "not_verified",
            "log": log + "\n[ERROR] 설치 상태 확인 실패"
        }

    # 7. 최종 설치 결과 반환
    return {
        "profile": profile,
        "status": status,
        "installed_version": version_match.group(1),
        "verification": "verified",
        "log": log
    }